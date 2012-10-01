#!/usr/bin/python
"""
This is the main script for WCGBrowser, a kiosk-oriented web browser
Written by Alan D Moore, http://www.alandmoore.com
Released under the GNU GPL v3
"""

# PyQT imports
from PyQt4.QtGui import QMainWindow, QAction, QIcon, QWidget, QApplication, QSizePolicy, QKeySequence, QToolBar
from PyQt4.QtCore import QUrl, SIGNAL, QTimer, QObject, QT_VERSION_STR, QEvent, Qt, QTemporaryFile, QDir
from PyQt4.QtWebKit import QWebView, QWebPage, QWebSettings
from PyQt4.QtNetwork import QNetworkRequest, QNetworkAccessManager

# Standard library imports
import sys
import os
import argparse
import yaml
import re
import subprocess
import datetime

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
    """This class is the main application class,
    it defines the GUI window for the browser"""
    def createAction(self, text, slot=None, shortcut=None, icon=None, tip=None, checkable=False, signal="triggered()"):
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
            self.connect(action, SIGNAL(signal), slot)
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
        self.whitelist = self.configuration.get("whitelist", False)



        #The following variable sets the error code when a page cannot be reached, either because of a generic 404, or because you've blocked it.
        # You can override it using the "page_unavailable_html" setting in the configuration file.
        self.html404 = """<h2>Sorry, can't go there</h2>
        <p>This page is not available on this computer.</p>
        <p>You can return to the <a href='%s'>start page</a>, or wait and I'll return you to the <a href='javascript: history.back();'>previous page</a>.</p>
        <script>setTimeout('history.back()', 5000);</script>
        """ % (self.start_url)
        if (self.configuration.get("page_unavailable_html")):
            try:
                html404 = open(self.configuration.get("page_unavailable_html"), 'r').read()
            except:
                html404 = None
                debug("Couldn't read file: %s" % self.configuration.get("page_unavailable_html"))
            self.html404 = html404 or self.html404

        #This string is shown when sites that should be reachable (e.g. the start page) aren't.  You might want to put in contact information for your tech support, etc.
        # You can override it use the "network_down_html" setting in the configuration file.
        self.html_network_down = """<h2>Network Error</h2><p>The start page, %s, cannot be reached.  This indicates a network connectivity problem.</p>
        <p>Staff, please check the following:</p>
        <ul>
        <li>Ensure the network connections at the computer and at the switch, hub, or wall panel are secure</li>
        <li>Restart the computer</li>
        <li>Ensure other systems at your location can access the same URL</li>
        </ul>
        <p>If you continue to get this error, contact technical support</p> """ % (self.start_url)
        if (self.configuration.get("network_down_html")):
            try:
                html_network_down = open(self.configuration.get("network_down_html"), 'r').read()
            except:
                html_network_down = None
                debug("Couldn't read file: %s" % self.configuration.get("network_down_html"))
            self.html_network_down = html_network_down or self.html_network_down

        self.build_ui(self.options, self.configuration)

    def build_ui(self, options, configuration):
        inactivity_timeout = options.timeout or int(configuration.get("timeout", 0))
        timeout_mode = configuration.get('timeout_mode', 'reset')
        self.icon_theme = options.icon_theme or configuration.get("icon_theme", None)
        self.zoomfactor = options.zoomfactor or float(configuration.get("zoom_factor") or 1.0)
        self.allow_popups = options.allow_popups or configuration.get("allow_popups", False)
        self.ssl_mode = (configuration.get("ssl_mode") in ['strict', 'ignore'] and configuration.get("ssl_mode")) or 'strict'
        self.is_fullscreen = options.is_fullscreen or configuration.get("fullscreen", False)
        self.show_navigation = not options.noNav and configuration.get('navigation', True)
        self.navigation_layout = configuration.get("navigation_layout", ['back', 'forward', 'refresh', 'stop', 'zoom_in', 'zoom_out', 'separator', 'bookmarks', 'separator', 'spacer', 'quit'])
        self.content_handlers = self.configuration.get("content_handlers", {})
        self.allow_external_content = options.allow_external_content or self.configuration.get("allow_external_content", False)
        self.allow_plugins = options.allow_plugins or self.configuration.get("allow_plugins", False)
        self.quit_button_mode = self.configuration.get("quit_button_mode", 'reset')
        self.quit_button_text = self.configuration.get("quit_button_text", "I'm &Finished")
        self.window_size = options.window_size or self.configuration.get("window_size", None)
        qb_mode_callbacks = {'close': self.close, 'reset': self.reset_browser}
        #If the whitelist is activated, add the bookmarks and start_url
        if self.whitelist:
            # we can just specify whitelist = True, which should whitelist just the start_url and bookmark urls.
            if type(self.whitelist) is not list:
                self.whitelist = []
            self.whitelist.append(str(QUrl(self.start_url).host()))
            bookmarks = self.configuration.get("bookmarks")
            if bookmarks:
                self.whitelist += [str(QUrl(b.get("url")).host()) for k,b in bookmarks.items()]
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
            whitelist = self.whitelist
            )

        #Supposedly this code will make certificates work, but I could never
        #get it to work right.  For now we're just ignoring them.

        ## config = QSslConfiguration.defaultConfiguration()
        ## certs = config.caCertificates()
        ## certs.append(QSslCertificate(QFile("somecert.crt")))
        ## config.setCaCertificates(certs)

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
                "Click here when you are done. \nIt will clear your browsing history and return you to the start page."
                )
            #Zoom buttons
            self.nav_items["zoom_in"] = self.createAction("Zoom In", self.zoom_in, QKeySequence("Alt++"), "zoom-in", "Increase the size of the text and images on the page")
            self.nav_items["zoom_out"] = self.createAction("Zoom Out", self.zoom_out, QKeySequence("Alt+-"), "zoom-out", "Decrease the size of text and images on the page")

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
                            #Create a button for the bookmark as a QAction, which we'll add to the toolbar
                            button = self.createAction(bookmark[0],
                                                       lambda url=bookmark[1].get("url"): self.browser_window.load(QUrl(url)),
                                                       QKeySequence.mnemonic(bookmark[0]),
                                                       None,
                                                       bookmark[1].get("description")
                                                       )
                            self.navigation_bar.addAction(button)
                else:
                    self.navigation_bar.addAction(self.nav_items.get(item, None))

            #This removes the ability to toggle off the navigation bar:
            self.nav_toggle = self.navigation_bar.toggleViewAction()
            self.nav_toggle.setVisible(False)
            #End "if show_navigation is True" block

        # set hidden quit action
        # For reasons I haven't adequately ascertained, this shortcut fails now and then claiming "Ambiguous shortcut overload".  No idea why, as it isn't consistent.
        self.really_quit = self.createAction("", self.close, QKeySequence("Ctrl+Alt+Q"), None, "")
        self.addAction(self.really_quit)

        #Call a reset function after timeout
        if inactivity_timeout != 0:
            self.event_filter = InactivityFilter(inactivity_timeout)
            self.installEventFilter(self.event_filter)
            self.browser_window.page().installEventFilter(self.event_filter)
            self.connect(self.event_filter, SIGNAL("timeout()"), qb_mode_callbacks.get(timeout_mode, self.reset_browser))
        ###END OF CONSTRUCTOR###

    def reset_browser(self):
        # self.navigation_bar.clear() doesn't do its job, so remove the toolbar first, then rebuild the UI.
        debug("RESET BROWSER")
        self.removeToolBar(self.navigation_bar)
        self.build_ui(self.options, self.configuration)

    def zoom_in(self):
        """This is the callback for the zoom in action.  Note that we cap zooming in at a factor of 3x."""
        if self.browser_window.zoomFactor() < 3.0:
            self.browser_window.setZoomFactor(self.browser_window.zoomFactor() + 0.1)
            self.nav_items["zoom_out"].setEnabled(True)
        else:
            self.nav_items["zoom_in"].setEnabled(False)

    def zoom_out(self):
        """This is the callback for the zoom out action.  Note that we cap zooming out at 0.1x."""
        if self.browser_window.zoomFactor() > 0.1:
            self.browser_window.setZoomFactor(self.browser_window.zoomFactor() - 0.1)
            self.nav_items["zoom_in"].setEnabled(True)
        else:
            self.nav_items["zoom_out"].setEnabled(False)



### END Main Application Window Class def ###

class InactivityFilter(QTimer):
    """This class defines an inactivity filter, which is basically a timer that resets every time "activity" events are detected in the main application."""
    def __init__(self, timeout=0, parent=None):
        super(InactivityFilter, self).__init__(parent)
        self.timeout = timeout * 1000  # timeout needs to be converted from seconds to milliseconds
        self.setInterval(self.timeout)
        self.start()

    def eventFilter(self, object, event):
        if event.type() in (QEvent.HoverMove, QEvent.KeyPress, QEvent.KeyRelease, ):
            self.emit(SIGNAL("activity"))
            self.start(self.timeout)
            #commented this debug code, because it spits out way to much information.
            #uncomment if you're having trouble with the timeout detecting user inactivity correctly to determine what it's detecting and ignoring
            #debug ("Activity: %s type %d" % (event, event.type()))
        #else:
            #debug("Ignored event: %s type %d" % (event, event.type()))
        return QObject.eventFilter(self, object, event)


class WcgWebView(QWebView):
    """This is the webview for the application.  It's a simple wrapper around QWebView that configures some basic settings."""
    def __init__(self, parent=None, **kwargs):
        super(WcgWebView, self).__init__(parent)
        self.kwargs = kwargs
        self.nam = kwargs.get('networkAccessManager') or QNetworkAccessManager()
        self.page().setNetworkAccessManager(self.nam)
        self.allow_popups = kwargs.get('allow_popups')
        self.default_user = kwargs.get('default_user', '')
        self.default_password = kwargs.get('default_password', '')
        self.allow_plugins = kwargs.get("allow_plugins", False)
        self.settings().setAttribute(QWebSettings.JavascriptCanOpenWindows, self.allow_popups)
        #JavascriptCanCloseWindows is in the API documentation, but my system claims QWebSettings has no such member.
        #self.settings().setAttribute(QWebSettings.JavascriptCanCloseWindows, self.allow_popups)
        self.settings().setAttribute(QWebSettings.PrivateBrowsingEnabled, True)
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

        #connections for wcgwebview
        self.connect(self.page().networkAccessManager(), SIGNAL("authenticationRequired(QNetworkReply * , QAuthenticator *)"), self.auth_dialog)
        self.connect(self.page(), SIGNAL("unsupportedContent(QNetworkReply *)"), self.handle_unsupported_content)
        self.connect(self.page().networkAccessManager(), SIGNAL("sslErrors (QNetworkReply *, const QList<QSslError> &)"), self.sslErrorHandler)
        self.connect(self, SIGNAL("urlChanged(QUrl)"), self.onLinkClick)
        self.connect(self, SIGNAL("loadFinished(bool)"), self.onLoadFinished)

    def createWindow(self, type):
        """This function has been overridden to allow for popup windows, if that feature is enabled."""
        if self.allow_popups:
            self.popup = WcgWebView(None, networkAccessManager=self.nam, **self.kwargs)
            #This assumes the window manager has an "X" icon for closing the window somewhere to the right.
            self.popup.setWindowTitle("Click the 'X' to close this window! ---> ")
            self.popup.show()
            return self.popup
        else:
            debug("Popup not loaded on %s" % self.url().toString())

    #sslErrorHandler was overridden to ignore SSL errors, because I couldn't make certificates work.
    #Obviously, if you're in an environment where this could be a security risk, this is bad.
    def sslErrorHandler(self, reply, errorList):
        if self.ssl_mode == 'ignore':
            reply.ignoreSslErrors()
            debug("SSL error ignored")
            debug(", ".join([str(error.errorString()) for error in errorList]))
        else:
            self.setHtml("""<h1>Certificate Problem</h1><p>The URL <strong>%s</strong> has a problem with its SSL certificate.  For your security and protection, you will not be able to access it from this browser.</p><p>If this URL is supposed to be reachable, please contact technical support for help.</p> <p>You may <a href="%s">click here</a> to return to the home screen.</p>""" % (reply.url().toString(), self.start_url))

    def auth_dialog(self, reply, authenticator):
        """This is called when a page requests authentication.  It might be nice to actually have a dialog here, but for now we just use the default credentials from the config file."""
        debug("Auth required on %s" % reply.url().toString())
        authenticator.setUser(self.default_user)
        authenticator.setPassword(self.default_password)

    def handle_unsupported_content(self, reply):
        """Called basically when the reply from the request is not HTML or something else renderable by qwebview"""
        self.reply = reply
        self.content_type = self.reply.header(QNetworkRequest.ContentTypeHeader).toString()
        self.content_filename = re.match('.*;\s*filename=(.*);', self.reply.rawHeader('Content-Disposition'))
        self.content_filename = QUrl.fromPercentEncoding((self.content_filename and self.content_filename.group(1)) or '')
        content_url = self.reply.url()
        debug("Loading url %s of type %s" % (content_url.toString(), self.content_type))
        if not self.content_handlers.get(str(self.content_type)):
            self.setHtml("<h1>Failed: unrenderable content</h1><p>The browser does not know how to handle the content type <strong>%s</strong> of the file <strong>%s</strong> supplied by <strong>%s</strong>.</p>" % (self.content_type, self.content_filename, content_url.toString()))
        else:
            if str(self.url().toString()) in ('', 'about:blank'):
                self.setHtml("<H1>Downloading</h1><p>Please wait while the file <strong>%s</strong> (%s) downloads from <strong>%s</strong>." % (self.content_filename, self.content_type, content_url.toString()))
            else:
                # print(self.url())
                self.load(self.url())
            self.connect(self.reply, SIGNAL("finished()"), self.display_downloaded_content)

    def display_downloaded_content(self):
        """Called when an unsupported content type is finished downloading."""
        file_path = QDir.toNativeSeparators(QDir.tempPath() + "/XXXXXX_" + self.content_filename)
        myfile = QTemporaryFile(file_path)
        myfile.setAutoRemove(False)
        if (myfile.open()):
            myfile.write(self.reply.readAll())
            myfile.close()
            subprocess.Popen([self.content_handlers.get(str(self.content_type)), myfile.fileName()])

            #Sometimes downloading files opens an empty window.  So if the current window has no URL, close it.
            if(str(self.url().toString()) in ('', 'about:blank')):
                self.close()

    def onLinkClick(self, url):
        #If whitelisting is enabled, and this isn't the start_url host, check the url to see if the host's domain matches.
        if self.whitelist and not (url.host() == QUrl(self.start_url).host()) and not str(url.toString()) == 'about:blank':
            site_ok = False
            for whitelisted_host in self.whitelist:
                pattern = str("(^|.*\.)" + whitelisted_host + "$")
                if re.match(pattern, url.host()):
                    site_ok = True
            if not site_ok:
                self.setHtml(self.html404)
        if not url.isValid():
            debug("Invalid URL %s" % url.toString())
        else:
            debug("Load URL %s" % url.toString())

    def onLoadFinished(self, ok):
        """This function is called when a page load finishes.  We're checking to see if the load was successful; if it's not, we display either the 404 error, or a "network is down" message if it's the start page that failed or some random page."""
        if not ok:
            if self.url().host() == QUrl(self.start_url).host() and str(self.url().path()).rstrip("/") == str(QUrl(self.start_url).path()).rstrip("/"):
                self.setHtml(self.html_network_down, QUrl())
                debug("Start Url doesn't seem to be available; displaying error")
            else:
                debug("404 on URL: %s" % self.url().toString())
                self.setHtml(self.html404, QUrl())
        return True
#### END WCGWEBVIEW DEFINITION ####

######### Main application code begins here ###################


def main(args):
    app = QApplication(sys.argv)
    mainwin = MainWindow(args)
    mainwin.show()
    app.exec_()

if __name__ == "__main__":
    #locate the configuration file to use.
    if os.path.isfile(os.path.expanduser("~/.wcgbrowser.yaml")):
        default_config_file = os.path.expanduser("~/.wcgbrowser.yaml")
    elif os.path.isfile("/etc/wcgbrowser.yaml"):
        default_config_file = "/etc/wcgbrowser.yaml"
    else:
        default_config_file = None

    #Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--url", action="store", dest="url", help="Start browser at URL")
    parser.add_argument("-f", "--fullscreen", action="store_true", default=False, dest="is_fullscreen", help="Start browser FullScreen")
    parser.add_argument("-n", "--no-navigation", action="store_true", default=False, dest="noNav", help="Start browser without Navigation controls")
    parser.add_argument("-c", "--config-file", action="store", default=default_config_file, dest="config_file", help="Specifiy an alternate config file")
    parser.add_argument("-d", "--debug", action="store_true", default=False, dest="DEBUG", help="Enable debugging output to stdout")
    parser.add_argument("--debug_log", action="store", default=None, dest="debug_log", help="Enable debug output to the specified filename")
    parser.add_argument("-t", "--timeout", action="store", type=int, default=0, dest="timeout", help="Define the timeout in seconds after which to reset the browser due to user inactivity")
    parser.add_argument("-i", "--icon-theme", action="store", default=None, dest="icon_theme", help="override default icon theme with other Qt/KDE icon theme")
    parser.add_argument("-z", "--zoom", action="store", type=float, default=0, dest="zoomfactor", help="Set the zoom factor for web pages")
    parser.add_argument("-p", "--popups", action="store_true", default=False, dest="allow_popups", help="Allow the browser to open new windows")
    parser.add_argument("-u", "--user", action="store", dest="default_user", help="Set the default username used for URLs that require authentication")
    parser.add_argument("-w", "--password", action="store", dest="default_password", help="Set the default password used for URLs that require authentication")
    parser.add_argument("-e", "--allow_external", action="store_true", default=False, dest='allow_external_content', help="Allow the browser to open content in external programs.")
    parser.add_argument("-g", "--allow_plugins", action="store_true", default=False, dest='allow_plugins', help="Allow the browser to use plugins like Flash or Java (if installed)")
    parser.add_argument("--size", action="store", dest="window_size", default=None, help="Specify the default window size in pixels (widthxheight), or 'max' to maximize")
    args = parser.parse_args()
    DEBUG = args.DEBUG
    DEBUG_LOG = args.debug_log
    if not args.config_file:
        debug ("No config file found or specified; using defaults.")

    #run the actual application
    main(args)
