#!/usr/bin/python
"""
This is the main script for WCGBrowser, a kiosk-oriented web browser
Written by Alan D Moore, http://www.alandmoore.com
Released under the GNU GPL v3
"""

# PyQT5 imports

try:
    from PyQt5.QtGui import QIcon, QKeySequence
    from PyQt5.QtCore import QUrl, QTimer, QObject, QT_VERSION_STR, QEvent, Qt, QTemporaryFile, QDir, QCoreApplication, qVersion, pyqtSignal
    from PyQt5.QtWebKit import QWebSettings
    from PyQt5.QtWidgets import QMainWindow, QAction, QWidget, QApplication, QSizePolicy, QToolBar, QDialog, QMenu
    from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
    from PyQt5.QtWebKitWidgets import QWebView, QWebPage
    from PyQt5.QtNetwork import QNetworkRequest, QNetworkAccessManager, QNetworkProxy

except ImportError:
    # If not PyQt5, try PyQt4
    try:
        from PyQt4.QtGui import QMainWindow, QAction, QIcon, QWidget, QApplication,\
            QSizePolicy, QKeySequence, QToolBar, QPrinter, QPrintDialog, QDialog, QMenu
        from PyQt4.QtCore import QUrl, QTimer, QObject, QT_VERSION_STR, QEvent, \
            Qt, QTemporaryFile, QDir, QCoreApplication, qVersion, pyqtSignal
        from PyQt4.QtWebKit import QWebView, QWebPage, QWebSettings
        from PyQt4.QtNetwork import QNetworkRequest, QNetworkAccessManager, QNetworkProxy

    except ImportError:
        """If not PyQT, try PySide"""
        from PySide.QtGui import QMainWindow, QAction, QIcon, QWidget, QApplication,\
             QSizePolicy, QKeySequence, QToolBar, QPrinter, QPrintDialog, QDialog, QMenu
        from PySide.QtCore import QUrl, QTimer, QObject, QEvent, \
             Qt, QTemporaryFile, QDir, QCoreApplication, qVersion, pyqtSignal
        from PySide.QtWebKit import QWebView, QWebPage, QWebSettings
        from PySide.QtNetwork import QNetworkRequest, QNetworkAccessManager, QNetworkProxy
        QT_VERSION_STR = qVersion()




# Standard library imports
import sys
import os
import argparse
import yaml
import re
import subprocess
import datetime

#MESSAGE STRINGS
DEFAULT_404 = """<h2>Sorry, can't go there</h2>
<p>This page is not available on this computer.</p>
<p>You can return to the <a href='%s'>start page</a>,
or wait and you'll be returned to the
<a href='javascript: history.back();'>previous page</a>.</p>
<script>setTimeout('history.back()', 5000);</script>
"""

DEFAULT_NETWORK_DOWN =  """<h2>Network Error</h2>
<p>The start page, %s, cannot be reached.
This indicates a network connectivity problem.</p>
<p>Staff, please check the following:</p>
<ul>
<li>Ensure the network connections at the computer and at the switch,
hub, or wall panel are secure</li>
<li>Restart the computer</li>
<li>Ensure other systems at your location can access the same URL</li>
</ul>
<p>If you continue to get this error, contact technical support</p> """

CERTIFICATE_ERROR = """<h1>Certificate Problem</h1>
<p>The URL <strong>%s</strong> has a problem with its SSL certificate.
For your security and protection, you will not be able to access it from this browser.</p>
<p>If this URL is supposed to be reachable, please contact technical support for help.</p>
<p>You can return to the <a href='%s'>start page</a>, or wait and
you'll be returned to the <a href='javascript: history.back();'>previous page</a>.</p>
<script>setTimeout('history.back()', 5000);</script>
"""

UNKNOWN_CONTENT_TYPE = """<h1>Failed: unrenderable content</h1>
<p>The browser does not know how to handle the content type
<strong>%s</strong> of the file <strong>%s</strong> supplied by
<strong>%s</strong>.</p>"""

DOWNLOADING_MESSAGE = """<H1>Downloading</h1>
<p>Please wait while the file <strong>%s</strong> (%s)
downloads from <strong>%s</strong>."""

def debug(message):
    if not DEBUG and not DEBUG_LOG:
        pass
    else:
        message = message.__str__()
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        debug_message = ts + ":: " + message
        if DEBUG:
            print (debug_message)
        if DEBUG_LOG:
            try:
                fh = open(DEBUG_LOG, 'a')
                fh.write(debug_message + "\n")
                fh.close
            except:
                print ("unable to write to log file %s" % DEBUG_LOG)

class MainWindow(QMainWindow):
    """
    This class is the main application class,
    it defines the GUI window for the browser
    """
    def createAction(self, text, slot=None, shortcut=None, icon=None, tip=None,
                     checkable=False, signal="triggered"):
        """Borrowed from 'Rapid GUI Development with PyQT by Mark Summerset'"""
        action = QAction(text, self)
        if icon is not None:
            action.setIcon(QIcon.fromTheme(icon, QIcon(":/%s.png" % icon)))
        if shortcut is not None and not shortcut.isEmpty():
            action.setShortcut(shortcut)
            tip += " (%s)" % shortcut.toString()
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None:
            action.__getattr__(signal).connect(slot)
        if checkable:
            action.setCheckable()
        return action

    def __init__(self, options, parent=None):
        super(MainWindow, self).__init__(parent)
        #Load config file
        self.setWindowTitle("Browser")
        self.options = options
        self.configuration = {}
        debug("loading configuration from '%s'" % options.config_file)
        if self.options.config_file:
            self.configuration = yaml.safe_load(open(self.options.config_file, 'r'))
        debug(self.configuration)
        self.default_user = options.default_user or  self.configuration.get("default_user")
        self.default_password = options.default_password or self.configuration.get("default_password")
        self.start_url = options.url or self.configuration.get("start_url", "about:blank")
        self.screensaver_url = self.configuration.get("screensaver_url", "about:blank")
        self.screensaver_active = False
        self.whitelist = self.configuration.get("whitelist", False)
        self.proxy_server = options.proxy_server or os.environ.get("http_proxy") or self.configuration.get("proxy_server")
        self.popup = None

        # Stylesheet support
        self.stylesheet = self.configuration.get("stylesheet")
        if self.stylesheet:
            try:
                with open(self.stylesheet) as ss:
                    self.setStyleSheet(ss.read())
            except:
                debug("""Problem loading stylesheet file "%s", using default style.""" % self.stylesheet)
        self.setObjectName("global")

        #The following variable sets the error code when a page cannot be reached,
        # either because of a generic 404, or because you've blocked it.
        # You can override it using the "page_unavailable_html" setting in the configuration file.
        self.html404 = DEFAULT_404 % (self.start_url)
        if (self.configuration.get("page_unavailable_html")):
            try:
                html404 = open(self.configuration.get("page_unavailable_html"), 'r').read()
            except:
                html404 = None
                debug("Couldn't read file: %s" % self.configuration.get("page_unavailable_html"))
            self.html404 = html404 or self.html404

        #This string is shown when sites that should be reachable (e.g. the start page) aren't.
        #You might want to put in contact information for your tech support, etc.
        # You can override it use the "network_down_html" setting in the configuration file.
        self.html_network_down = DEFAULT_NETWORK_DOWN % (self.start_url)
        if (self.configuration.get("network_down_html")):
            try:
                html_network_down = open(self.configuration.get("network_down_html"), 'r').read()
            except:
                html_network_down = None
                debug("Couldn't read file: %s" % self.configuration.get("network_down_html"))
            self.html_network_down = html_network_down or self.html_network_down

        self.build_ui(self.options, self.configuration)

    def build_ui(self, options, configuration):
        """
        This is all the twisted logic of setting up the UI, which is re-run
        whenever the browser is "reset" by the user.
        """
        debug("build_ui")
        inactivity_timeout = options.timeout or int(configuration.get("timeout", 0))
        timeout_mode = configuration.get('timeout_mode', 'reset')
        self.icon_theme = options.icon_theme or configuration.get("icon_theme", None)
        self.zoomfactor = options.zoomfactor or float(configuration.get("zoom_factor") or 1.0)
        self.allow_popups = options.allow_popups or configuration.get("allow_popups", False)
        self.ssl_mode = (configuration.get("ssl_mode") in ['strict', 'ignore'] and configuration.get("ssl_mode")) or 'strict'
        self.is_fullscreen = options.is_fullscreen or configuration.get("fullscreen", False)
        self.show_navigation = not options.no_navigation and configuration.get('navigation', True)
        self.navigation_layout = configuration.get(
            "navigation_layout",
            ['back', 'forward', 'refresh', 'stop', 'zoom_in', 'zoom_out',
             'separator', 'bookmarks', 'separator', 'spacer', 'quit'])
        self.content_handlers = self.configuration.get("content_handlers", {})
        self.allow_external_content = options.allow_external_content or self.configuration.get("allow_external_content", False)
        self.allow_plugins = options.allow_plugins or self.configuration.get("allow_plugins", False)
        self.privacy_mode = self.configuration.get("privacy_mode", True)
        self.quit_button_mode = self.configuration.get("quit_button_mode", 'reset')
        self.quit_button_text = self.configuration.get("quit_button_text", "I'm &Finished")
        self.quit_button_tooltip = (self.quit_button_mode == 'close' and "Click here to quit the browser.") or \
        """Click here when you are done.\nIt will clear your browsing history and return you to the start page."""
        self.window_size = options.window_size or self.configuration.get("window_size", None)
        self.allow_printing = self.configuration.get("allow_printing", False)
        self.print_settings = self.configuration.get("print_settings", "{}")
        self.user_agent = self.configuration.get("user_agent", None)
        qb_mode_callbacks = {'close': self.close, 'reset': self.reset_browser}
        to_mode_callbacks = {'close': self.close, 'reset': self.reset_browser, 'screensaver': self.screensaver}


        #If the whitelist is activated, add the bookmarks and start_url
        if self.whitelist:
            # we can just specify whitelist = True,
            #which should whitelist just the start_url and bookmark urls.
            if type(self.whitelist) is not list:
                self.whitelist = []
            self.whitelist.append(str(QUrl(self.start_url).host()))
            bookmarks = self.configuration.get("bookmarks")
            if bookmarks:
                self.whitelist += [str(QUrl(b.get("url")).host()) for k,b in bookmarks.items()]
                self.whitelist = list(set(self.whitelist)) #uniquify
                self.whitelist = [item.replace(".", "\.") for item in self.whitelist] #escape dots
            debug("Generated whitelist: " + str(self.whitelist))

        ###Start GUI configuration###
        self.browser_window = WcgWebView(
            allow_popups=self.allow_popups,
            default_user=self.default_user,
            default_password=self.default_password,
            zoomfactor=self.zoomfactor,
            content_handlers=self.content_handlers,
            allow_external_content=self.allow_external_content,
            html404=self.html404,
            html_network_down=self.html_network_down,
            start_url=self.start_url,
            ssl_mode=self.ssl_mode,
            allow_plugins = self.allow_plugins,
            whitelist = self.whitelist,
            allow_printing = self.allow_printing,
            print_settings = self.print_settings,
            proxy_server = self.proxy_server,
            privacy_mode = self.privacy_mode,
            user_agent = self.user_agent
            )
        self.browser_window.setObjectName("web_content")

        if self.icon_theme is not None and QT_VERSION_STR > '4.6':
            QIcon.setThemeName(self.icon_theme)
        self.setCentralWidget(self.browser_window)
        debug(options)
        debug("loading %s" % self.start_url)
        self.browser_window.setUrl(QUrl(self.start_url))
        if self.is_fullscreen is True:
            self.showFullScreen()
        elif self.window_size and self.window_size.lower() == 'max':
            self.showMaximized()
        elif self.window_size:
            size = re.match(r"(\d+)x(\d+)", self.window_size)
            if size:
                width, height = size.groups()
                self.setFixedSize(int(width), int(height))
            else:
                debug("Ignoring invalid window size \"%s\"" % self.window_size)

        #Set up the top navigation bar if it's configured to exist
        if self.show_navigation is True:
            self.navigation_bar = QToolBar("Navigation")
            self.navigation_bar.setObjectName("navigation")
            self.addToolBar(Qt.TopToolBarArea, self.navigation_bar)
            self.navigation_bar.setMovable(False)
            self.navigation_bar.setFloatable(False)

            #Standard navigation tools
            self.nav_items = {}
            self.nav_items["back"] = self.browser_window.pageAction(QWebPage.Back)
            self.nav_items["forward"] = self.browser_window.pageAction(QWebPage.Forward)
            self.nav_items["refresh"] = self.browser_window.pageAction(QWebPage.Reload)
            self.nav_items["stop"] = self.browser_window.pageAction(QWebPage.Stop)
            #The "I'm finished" button.
            self.nav_items["quit"] = self.createAction(
                self.quit_button_text,
                qb_mode_callbacks.get(self.quit_button_mode, self.reset_browser),
                QKeySequence("Alt+F"),
                None,
                self.quit_button_tooltip)
            #Zoom buttons
            self.nav_items["zoom_in"] = self.createAction(
                "Zoom In",
                self.zoom_in,
                QKeySequence("Alt++"),
                "zoom-in",
                "Increase the size of the text and images on the page")
            self.nav_items["zoom_out"] = self.createAction(
                "Zoom Out",
                self.zoom_out,
                QKeySequence("Alt+-"),
                "zoom-out",
                "Decrease the size of text and images on the page")
            if self.allow_printing:
                self.nav_items["print"] = self.createAction("Print", self.browser_window.print_webpage, QKeySequence("Ctrl+p"), "document-print", "Print this page")

            #Add all the actions to the navigation bar.
            for item in self.navigation_layout:
                if item == "separator":
                    self.navigation_bar.addSeparator()
                elif item == "spacer":
                    #an expanding spacer.
                    spacer = QWidget()
                    spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    self.navigation_bar.addWidget(spacer)
                elif item == "bookmarks":
                    #Insert bookmarks buttons here.
                    self.bookmark_buttons = []
                    if configuration.get("bookmarks"):
                        for bookmark in configuration.get("bookmarks").items():
                            debug("Bookmark:\n" + bookmark.__str__())
                            #bookmark name will use the "name" attribute, if present
                            #or else just the key:
                            bookmark_name = bookmark[1].get("name") or bookmark[0]
                            #Create a button for the bookmark as a QAction,
                            #which we'll add to the toolbar
                            button = self.createAction(
                                bookmark_name,
                                lambda url=bookmark[1].get("url"): self.browser_window.load(QUrl(url)),
                                QKeySequence.mnemonic(bookmark_name),
                                None,
                                bookmark[1].get("description")
                                )
                            self.navigation_bar.addAction(button)
                            self.navigation_bar.widgetForAction(button).setObjectName("navigation_button")
                else:
                    action = self.nav_items.get(item, None)
                    if action:
                        self.navigation_bar.addAction(action)
                        self.navigation_bar.widgetForAction(action).setObjectName("navigation_button")

            #This removes the ability to toggle off the navigation bar:
            self.nav_toggle = self.navigation_bar.toggleViewAction()
            self.nav_toggle.setVisible(False)
            #End "if show_navigation is True" block

        # set hidden quit action
        # For reasons I haven't adequately ascertained,
        #this shortcut fails now and then claiming "Ambiguous shortcut overload".
        # No idea why, as it isn't consistent.
        self.really_quit = self.createAction("", self.close, QKeySequence("Ctrl+Alt+Q"), None, "")
        self.addAction(self.really_quit)

        #Call a reset function after timeout
        if inactivity_timeout != 0:
            self.event_filter = InactivityFilter(inactivity_timeout)
            QCoreApplication.instance().installEventFilter(self.event_filter)
            self.browser_window.page().installEventFilter(self.event_filter)
            self.event_filter.timeout.connect(to_mode_callbacks.get(timeout_mode, self.reset_browser))
        else:
            self.event_filter = None

        ###END OF CONSTRUCTOR###

    def screensaver(self):
        debug("screensaver started")
        self.screensaver_active = True
        if self.popup:
            self.popup.close()
        if self.show_navigation is True:
            self.navigation_bar.hide()
        self.browser_window.setZoomFactor(self.zoomfactor)
        self.browser_window.load(QUrl(self.screensaver_url))
        self.event_filter.activity.disconnect()
        self.event_filter.activity.connect(self.reset_browser)

    def reset_browser(self):
        """
        This function clears the history and resets the UI.
        It's called whenever the inactivity filter times out,
        Or when the user clicks the "finished" button when in
        'reset' mode.
        """
        # Clear out the memory cache
        QWebSettings.clearMemoryCaches()
        self.browser_window.history().clear()
        # self.navigation_bar.clear() doesn't do its job,
        #so remove the toolbar first, then rebuild the UI.
        debug("RESET BROWSER")
        if self.event_filter:
            self.event_filter.blockSignals(True)
        if self.screensaver_active is True:
            self.screensaver_active = False
            self.event_filter.activity.disconnct()
        if self.event_filter:
            self.event_filter.blockSignals(False)
        if hasattr(self, "navigation_bar"):
            self.removeToolBar(self.navigation_bar)
        self.build_ui(self.options, self.configuration)

    def zoom_in(self):
        """
        This is the callback for the zoom in action.
        Note that we cap zooming in at a factor of 3x.
        """
        if self.browser_window.zoomFactor() < 3.0:
            self.browser_window.setZoomFactor(self.browser_window.zoomFactor() + 0.1)
            self.nav_items["zoom_out"].setEnabled(True)
        else:
            self.nav_items["zoom_in"].setEnabled(False)

    def zoom_out(self):
        """
        This is the callback for the zoom out action.
        Note that we cap zooming out at 0.1x.
        """
        if self.browser_window.zoomFactor() > 0.1:
            self.browser_window.setZoomFactor(self.browser_window.zoomFactor() - 0.1)
            self.nav_items["zoom_in"].setEnabled(True)
        else:
            self.nav_items["zoom_out"].setEnabled(False)



### END Main Application Window Class def ###

class InactivityFilter(QTimer):
    """
    This class defines an inactivity filter,
    which is basically a timer that resets every time "activity"
    events are detected in the main application.
    """
    activity = pyqtSignal()

    def __init__(self, timeout=0, parent=None):
        super(InactivityFilter, self).__init__(parent)
        # timeout needs to be converted from seconds to milliseconds
        self.timeout_time = timeout * 1000
        self.setInterval(self.timeout_time)
        self.start()

    def eventFilter(self, object, event):
        if event.type() in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.HoverMove, QEvent.KeyPress, QEvent.KeyRelease, ):
            self.activity.emit()
            self.start(self.timeout_time)
            #commented this debug code, because it spits out way to much information.
            #uncomment if you're having trouble with the timeout detecting user
            #inactivity correctly to determine what it's detecting and ignoring
            #debug ("Activity: %s type %d" % (event, event.type()))
            #else:
            #debug("Ignored event: %s type %d" % (event, event.type()))
        return QObject.eventFilter(self, object, event)


class WcgWebView(QWebView):
    """
    This is the webview for the application.
    It's a simple wrapper around QWebView that configures some basic settings.
    """
    def __init__(self, parent=None, **kwargs):
        super(WcgWebView, self).__init__(parent)
        self.kwargs = kwargs
        self.nam = kwargs.get('networkAccessManager') or QNetworkAccessManager()
        self.setPage(WCGWebPage())
        self.page().setNetworkAccessManager(self.nam)
        self.allow_popups = kwargs.get('allow_popups')
        self.default_user = kwargs.get('default_user', '')
        self.default_password = kwargs.get('default_password', '')
        self.allow_plugins = kwargs.get("allow_plugins", False)
        self.allow_printing = kwargs.get("allow_printing", False)
        self.settings().setAttribute(QWebSettings.JavascriptCanOpenWindows, self.allow_popups)
        #JavascriptCanCloseWindows is in the API documentation, but apparently only exists after 4.8
        if QT_VERSION_STR >= '4.8':
            self.settings().setAttribute(QWebSettings.JavascriptCanCloseWindows, self.allow_popups)
        self.settings().setAttribute(QWebSettings.PrivateBrowsingEnabled, kwargs.get("privacy_mode", True))
        self.settings().setAttribute(QWebSettings.LocalStorageEnabled, True)
        self.settings().setAttribute(QWebSettings.PluginsEnabled, self.allow_plugins)
        self.zoomfactor = kwargs.get("zoomfactor", 1)
        self.allow_external_content = kwargs.get('allow_external_content')
        self.page().setForwardUnsupportedContent(self.allow_external_content)
        self.content_handlers = kwargs.get("content_handlers", {})
        self.setZoomFactor(self.zoomfactor)
        self.html404 = kwargs.get("html404", '')
        self.html_network_down = kwargs.get("html_network_down", '')
        self.start_url = kwargs.get("start_url", '')
        self.ssl_mode = kwargs.get("ssl_mode", "strict")
        self.whitelist = kwargs.get("whitelist", False)
        self.proxy_server = kwargs.get("proxy_server")

        #add printing to context menu if it's allowed
        if self.allow_printing:
            self.print_action = QAction("Print", self)
            self.print_action.setIcon(QIcon.fromTheme("document-print"))
            self.print_action.triggered.connect(self.print_webpage)
            self.page().printRequested.connect(self.print_webpage)
            self.print_action.setToolTip("Print this web page")

            #Set up the proxy if there is one set
        if self.proxy_server:
            if ":" in self.proxy_server:
                proxyhost, proxyport = self.proxy_server.split(":")
            else:
                proxyhost = self.proxy_server
                proxyport = 8080
            self.nam.setProxy(QNetworkProxy(QNetworkProxy.HttpProxy, proxyhost, int(proxyport)))

        #connections for wcgwebview
        self.page().networkAccessManager().authenticationRequired.connect(self.auth_dialog)
        self.page().unsupportedContent.connect(self.handle_unsupported_content)
        self.page().networkAccessManager().sslErrors.connect(self.sslErrorHandler)
        self.urlChanged.connect(self.onLinkClick)
        self.loadFinished.connect(self.onLoadFinished)

    def createWindow(self, type):
        """
        This function has been overridden to allow for popup windows,
        if that feature is enabled.
        """
        if self.allow_popups:
            self.popup = WcgWebView(None, networkAccessManager=self.nam, **self.kwargs)
            # This assumes the window manager has an "X" icon
            # for closing the window somewhere to the right.
            self.popup.setObjectName("web_content")
            self.popup.setWindowTitle("Click the 'X' to close this window! ---> ")
            self.popup.show()
            return self.popup
        else:
            debug("Popup not loaded on %s" % self.url().toString())

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        for action in [QWebPage.Back, QWebPage.Forward, QWebPage.Reload, QWebPage.Stop]:
            action = self.pageAction(action)
            if action.isEnabled():
                menu.addAction(action)
        if self.allow_printing:
            menu.addAction(self.print_action)
        menu.exec_(event.globalPos())

    def sslErrorHandler(self, reply, errorList):
        """
        Called whenever the browser encounters an SSL error.
        Checks the ssl_mode and responds accordingly.
        """
        if self.ssl_mode == 'ignore':
            reply.ignoreSslErrors()
            debug("SSL error ignored")
            debug(", ".join([str(error.errorString()) for error in errorList]))
        else:
            self.setHtml(CERTIFICATE_ERROR % (reply.url().toString(), self.start_url))

    def auth_dialog(self, reply, authenticator):
        """
        This is called when a page requests authentication.
        It might be nice to actually have a dialog here,
        but for now we just use the default credentials from the config file.
        """
        debug("Auth required on %s" % reply.url().toString())
        if (self.default_user):
            authenticator.setUser(self.default_user)
        if (self.default_password):
            authenticator.setPassword(self.default_password)

    def handle_unsupported_content(self, reply):
        """
        Called basically when the reply from the request is not HTML
        or something else renderable by qwebview
        """
        self.reply = reply
        self.content_type = self.reply.header(QNetworkRequest.ContentTypeHeader).toString()
        self.content_filename = re.match('.*;\s*filename=(.*);', self.reply.rawHeader('Content-Disposition'))
        self.content_filename = QUrl.fromPercentEncoding((self.content_filename and self.content_filename.group(1)) or '')
        content_url = self.reply.url()
        debug("Loading url %s of type %s" % (content_url.toString(), self.content_type))
        if not self.content_handlers.get(str(self.content_type)):
            self.setHtml(UNKNOWN_CONTENT_TYPE % (self.content_type,
                                           self.content_filename,
                                           content_url.toString()))
        else:
            if str(self.url().toString()) in ('', 'about:blank'):
                self.setHtml(DOWNLOADING_MESSAGE % (self.content_filename,
                                                          self.content_type,
                                                          content_url.toString()))
            else:
                # print(self.url())
                self.load(self.url())
            self.reply.finished.connect(self.display_downloaded_content)

    def display_downloaded_content(self):
        """
        Called when an unsupported content type is finished downloading.
        """
        file_path = QDir.toNativeSeparators(QDir.tempPath() + "/XXXXXX_" + self.content_filename)
        myfile = QTemporaryFile(file_path)
        myfile.setAutoRemove(False)
        if (myfile.open()):
            myfile.write(self.reply.readAll())
            myfile.close()
            subprocess.Popen([self.content_handlers.get(str(self.content_type)), myfile.fileName()])

            #Sometimes downloading files opens an empty window.
            #So if the current window has no URL, close it.
            if(str(self.url().toString()) in ('', 'about:blank')):
                self.close()

    def onLinkClick(self, url):
        """
        Called whenever the browser navigates to a URL;
        handles the whitelisting logic.
        """
        debug("Request URL: %s" % url.toString())
        if not url.isEmpty():
            #If whitelisting is enabled, and this isn't the start_url host,
            #check the url to see if the host's domain matches.
            if self.whitelist \
                and not (url.host() == QUrl(self.start_url).host()) \
                and not str(url.toString()) == 'about:blank':
                site_ok = False
                pattern = re.compile(str("(^|.*\.)(" + "|".join(self.whitelist) + ")$"))
                if re.match(pattern, url.host()):
                    site_ok = True
                if not site_ok:
                    debug ("Site violates whitelist: %s" % url.toString)
                    self.setHtml(self.html404)
            if not url.isValid():
                debug("Invalid URL %s" % url.toString())
            else:
                debug("Load URL %s" % url.toString())

    def onLoadFinished(self, ok):
        """
        This function is called when a page load finishes.
        We're checking to see if the load was successful;
        if it's not, we display either the 404 error (if
        it's just some random page), or a "network is down" message
        (if it's the start page that failed).
        """
        if not ok:
            if self.url().host() == QUrl(self.start_url).host() \
              and str(self.url().path()).rstrip("/") == str(QUrl(self.start_url).path()).rstrip("/"):
                self.setHtml(self.html_network_down, QUrl())
                debug("Start Url doesn't seem to be available; displaying error")
            else:
                debug("404 on URL: %s" % self.url().toString())
                self.setHtml(self.html404, QUrl())
        return True

    def print_webpage(self):
        """
        Callback for the print action.  Should show a print dialog and print the webpage to the printer.
        """
        printer = QPrinter(mode = QPrinter.PrinterResolution)
        if self.print_settings:
            if self.print_settings.get("size_unit"):
                try:
                    unit = getattr(QPrinter, self.print_settings.get("size_unit").capitalize())
                except NameError:
                    debug("Specified print size unit '" + self.print_settings.get("size_unit") + "' not found, using default")
                    unit = QPrinter.Millimeter
            else:
                unit = QPrinter.Millimeter

            margins = self.print_settings.get("margins") or list(printer.getPageMargins(unit)):
            margins += [unit]
            printer.setPageMargins(*margins)

            if self.print_settings.get("orientation") == "landscape":
                printer.setOrientation(QPrinter.Landscape)
            else:
                printer.setOrientation(QPrinter.Portrait)

            if not self.print_settings.get("paper_size") == None:
                printer.setPaperSize(QSizeF(*self.print_settings.get("paper_size")), unit)

            if not self.print_settings.get("resolution") == None:
                printer.setResolution(int(self.print_settings.get("resolution")))

        if not self.print_settings.get("silent"):
            print_dialog = QPrintDialog(printer, self)
            print_dialog.setWindowTitle("Print Page")
            if not print_dialog.exec_() == QDialog.Accepted:
                return False

        self.print(printer)
        return True

#### END WCGWEBVIEW DEFINITION ####

#### WCGWEBPAGE #####

class WCGWebPage(QWebPage):
    """
    Subclassed QWebPage so that some functions can be overridden.
    """
    def __init__(self, parent=None):
        super(WCGWebPage, self).__init__(parent)
        self.user_agent = None

    def javaScriptConsoleMessage(self, message, line, sourceid):
        """
        Overridden so that we can send javascript errors to debug.
        """
        debug("Javascript Error in \"%s\" line %d: %s" % (sourceid, line, message))

    def userAgentForUrl(self, url):
        if self.user_agent: return self.user_agent
        else: return QWebPage.userAgentForUrl(self, url)

#### END WCGWEBPAGE DEFINITION ####

######### Main application code begins here ###################

if __name__ == "__main__":
    # Create the qapplication object, so it can interpret the qt-specific CLI args
    app = QApplication(sys.argv)

    #locate the configuration file to use.
    if os.path.isfile(os.path.expanduser("~/.wcgbrowser.yaml")):
        default_config_file = os.path.expanduser("~/.wcgbrowser.yaml")
    elif os.path.isfile("/etc/wcgbrowser.yaml"):
        default_config_file = "/etc/wcgbrowser.yaml"
    else:
        default_config_file = None

    #Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--url", action="store", dest="url",
                        help="Start browser at URL")
    parser.add_argument("-f", "--fullscreen", action="store_true", default=False,
                        dest="is_fullscreen", help="Start browser FullScreen")
    parser.add_argument("-n", "--no-navigation", action="store_true",
                        default=False, dest="no_navigation",
                        help="Start browser without Navigation controls")
    parser.add_argument("-c", "--config-file", action="store",
                        default=default_config_file, dest="config_file",
                        help="Specifiy an alternate config file")
    parser.add_argument("-d", "--debug", action="store_true",
                        default=False, dest="DEBUG",
                        help="Enable debugging output to stdout")
    parser.add_argument("--debug_log", action="store", default=None,
                        dest="debug_log",
                        help="Enable debug output to the specified filename")
    parser.add_argument("-t", "--timeout", action="store", type=int, default=0,
                        dest="timeout",
                        help="Define the timeout in seconds after which to reset the browser due to user inactivity")
    parser.add_argument("-i", "--icon-theme", action="store", default=None,
                        dest="icon_theme",
                        help="override default icon theme with other Qt/KDE icon theme")
    parser.add_argument("-z", "--zoom", action="store", type=float, default=0,
                        dest="zoomfactor", help="Set the zoom factor for web pages")
    parser.add_argument("-p", "--popups", action="store_true", default=False,
                        dest="allow_popups", help="Allow the browser to open new windows")
    parser.add_argument("-u", "--user", action="store", dest="default_user",
                        help="Set the default username used for URLs that require authentication")
    parser.add_argument("-w", "--password", action="store", dest="default_password",
                        help="Set the default password used for URLs that require authentication")
    parser.add_argument("-e", "--allow_external", action="store_true",
                        default=False, dest='allow_external_content',
                        help="Allow the browser to open content in external programs.")
    parser.add_argument("-g", "--allow_plugins", action="store_true",
                        default=False, dest='allow_plugins',
                        help="Allow the browser to use plugins like Flash or Java (if installed)")
    parser.add_argument("--size", action="store", dest="window_size",
                        default=None,
                        help="Specify the default window size in pixels (widthxheight), or 'max' to maximize")
    parser.add_argument("--proxy_server", action="store", dest="proxy_server", default=None,
                        help="Specify a proxy server string, in the form host:port")

    # rather than parse sys.argv here, we're parsing app.arguments so that qt-specific args are removed.
    # we also need to remove argument 0.
    args = parser.parse_args([str(x) for x in list(app.arguments())][1:])
    DEBUG = args.DEBUG
    DEBUG_LOG = args.debug_log
    if not args.config_file:
        debug ("No config file found or specified; using defaults.")

    #run the actual application
    mainwin = MainWindow(args)
    mainwin.show()
    app.exec_()
