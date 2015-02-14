#!/usr/bin/python
"""
This is the main script for WCGBrowser, a kiosk-oriented web browser
Written by Alan D Moore, http://www.alandmoore.com
Released under the GNU GPL v3
"""

# QT Binding imports

while True:
    # This is a little odd, but seemed cleaner than
    # progressively nesting try/except blocks.
    try:
        """Try to import PyQt5"""
        from PyQt5.QtGui import QIcon, QKeySequence
        from PyQt5.QtCore import (
            QUrl, QTimer, QObject, QT_VERSION_STR, QEvent,
            Qt, QTemporaryFile, QDir, QCoreApplication, qVersion, pyqtSignal,
            QSizeF
        )
        from PyQt5.QtWebKit import QWebSettings
        from PyQt5.QtWidgets import (
            QMainWindow, QAction, QWidget, QApplication, QSizePolicy,
            QToolBar, QDialog, QMenu
        )
        from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt5.QtWebKitWidgets import QWebView, QWebPage
        from PyQt5.QtNetwork import (QNetworkRequest, QNetworkAccessManager,
                                     QNetworkProxy)
        break
    except ImportError as e:
        print("QTt5 import error")
        pass
    try:
        """If not PyQt5, try PyQt4"""
        from PyQt4.QtGui import (
            QMainWindow, QAction, QIcon, QWidget,
            QApplication, QSizePolicy, QKeySequence, QToolBar, QPrinter,
            QPrintDialog, QDialog, QMenu
        )
        from PyQt4.QtCore import (
            QUrl, QTimer, QObject, QT_VERSION_STR, QEvent,
            Qt, QTemporaryFile, QDir, QCoreApplication, qVersion, pyqtSignal
        )
        from PyQt4.QtWebKit import QWebView, QWebPage, QWebSettings
        from PyQt4.QtNetwork import (
            QNetworkRequest, QNetworkAccessManager, QNetworkProxy
        )
        break
    except ImportError:
        pass
    try:
        """If not PyQT, try PySide"""
        from PySide.QtGui import (
            QMainWindow, QAction, QIcon, QWidget,
            QApplication, QSizePolicy, QKeySequence, QToolBar, QPrinter,
            QPrintDialog, QDialog, QMenu
        )
        from PySide.QtCore import (
            QUrl, QTimer, QObject, QEvent, Qt, QTemporaryFile,
            QDir, QCoreApplication, qVersion, pyqtSignal
        )
        from PySide.QtWebKit import QWebView, QWebPage, QWebSettings
        from PySide.QtNetwork import (
            QNetworkRequest, QNetworkAccessManager, QNetworkProxy
        )
        QT_VERSION_STR = qVersion()
        break
    except ImportError as e:
        print("You don't seem to have a QT library installed;"
              " please install PyQT or PySide.")
        exit(1)


# Standard library imports
import sys
import os
import argparse
import yaml
import re
import subprocess
import datetime

# MESSAGE STRINGS
# You can override this string with the "page_unavailable_html" setting.
# Just set it to a filename of the HTML you want to display.
# It will be formatted agains the configuration file, so you can
# include any config settings using {config_key_name}
DEFAULT_404 = """<h2>Sorry, can't go there</h2>
<p>This page is not available on this computer.</p>
<p>You can return to the <a href='{start_url}'>start page</a>,
or wait and you'll be returned to the
<a href='javascript: history.back();'>previous page</a>.</p>
<script>setTimeout('history.back()', 5000);</script>
"""

# This text will be shown when the start_url can't be loaded
# Usually indicates lack of network connectivity.
# It can be overridden by giving a filename in "network_down_html"
# and will be formatted against the config.

DEFAULT_NETWORK_DOWN = """<h2>Network Error</h2>
<p>The start page, {start_url}, cannot be reached.
This indicates a network connectivity problem.</p>
<p>Staff, please check the following:</p>
<ul>
<li>Ensure the network connections at the computer and at the switch,
hub, or wall panel are secure</li>
<li>Restart the computer</li>
<li>Ensure other systems at your location can access the same URL</li>
</ul>
<p>If you continue to get this error, contact technical support</p> """

# This is shown when an https site has a bad certificate and ssl_mode is set
# to "strict".

CERTIFICATE_ERROR = """<h1>Certificate Problem</h1>
<p>The URL <strong>{url}</strong> has a problem with its SSL certificate.
For your security and protection, you will not be able to access it from
 this browser.</p>
<p>If this URL is supposed to be reachable,
 please contact technical support for help.</p>
<p>You can return to the <a href='{start_url}'>start page</a>, or wait and
you'll be returned to the
 <a href='javascript: history.back();'>previous page</a>.</p>
<script>setTimeout('history.back()', 5000);</script>
"""

# Shown when content is requested that is not HTML, text, or
# something specified in the content handlers.

UNKNOWN_CONTENT_TYPE = """<h1>Failed: unrenderable content</h1>
<p>The browser does not know how to handle the content type
<strong>{mime_type}</strong> of the file <strong>{file_name}</strong>
 supplied by <strong>{url}</strong>.</p>"""

# This is displayed while a file is being downloaded.

DOWNLOADING_MESSAGE = """<H1>Downloading</h1>
<p>Please wait while the file <strong>{filename}</strong> ({mime_type})
downloads from <strong>{url}</strong>."""


def debug(message):
    """Log or print a message if the global DEBUG is true."""
    if not DEBUG and not DEBUG_LOG:
        pass
    else:
        message = message.__str__()
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        debug_message = ts + ":: " + message
        if DEBUG:
            print(debug_message)
        if DEBUG_LOG:
            try:
                fh = open(DEBUG_LOG, 'a')
                fh.write(debug_message + "\n")
                fh.close
            except:
                print("unable to write to log file {}".format(DEBUG_LOG))

# Define our default configuration settings
CONFIG_OPTIONS = {
    "allow_external_content": {"default": False, "type": bool},
    "allow_plugins":          {"default": False, "type": bool},
    "allow_popups":           {"default": False, "type": bool},
    "allow_printing":         {"default": False, "type": bool},
    "bookmarks":              {"default": {}, "type": dict},
    "content_handlers":       {"default": {}, "type": dict},
    "default_password":       {"default": None, "type": str},
    "default_user":           {"default": None, "type": str},
    "force_js_confirm":       {"default": "ask", "type": str,
                               "values": ("ask", "accept", "deny")},
    "fullscreen":             {"default": False, "type": bool},
    "icon_theme":             {"default": None, "type": str},
    "navigation":             {"default": True, "type": bool},
    "navigation_layout":      {"default":
                               ['back', 'forward', 'refresh', 'stop',
                                'zoom_in', 'zoom_out', 'separator',
                                'bookmarks', 'separator', 'spacer',
                                'quit'], "type": list},
    "network_down_html":      {"default": DEFAULT_NETWORK_DOWN,
                               "type": str, "is_file": True},
    "page_unavailable_html":  {"default": DEFAULT_404, "type": str,
                               "is_file": True},
    "print_settings":         {"default": None, "type": dict},
    "privacy_mode":           {"default": True, "type": bool},
    "proxy_server":           {"default": None, "type": str,
                               "env": "http_proxy"},
    "quit_button_mode":       {"default": "reset", "type": str,
                               "values": ["reset", "close"]},
    "quit_button_text":       {"default": "I'm &Finished", "type": str},
    "screensaver_url":        {"default": "about:blank", "type": str},
    "ssl_mode":               {"default": "strict", "type": str,
                               "values": ["strict", "ignore"]},
    "start_url":              {"default": "about:blank", "type": str},
    "stylesheet":             {"default": None, "type": str},
    "suppress_alerts":        {"default": False, "type": bool},
    "timeout":                {"default": 0, "type": int},
    "timeout_mode":           {"default": "reset", "type": str,
                               "values": ["reset", "close", "screensaver"]},
    "user_agent":             {"default": None, "type": str},
    "user_css":               {"default": None, "type": str},
    "whitelist":              {"default": None},  # don't check type here
    "window_size":            {"default": None},  # don't check type
    "zoom_factor":            {"default": 1.0, "type": float}
}


class MainWindow(QMainWindow):

    """This is the main application window class

    it defines the GUI window for the browser
    """

    def parse_config(self, file_config, options):
        self.config = {}
        options = vars(options)
        for key, metadata in CONFIG_OPTIONS.items():
            options_val = options.get(key)
            file_val = file_config.get(key)
            env_val = os.environ.get(metadata.get("env", ''))
            default_val = metadata.get("default")
            vals = metadata.get("values")
            debug("key: {}, default: {}, file: {}, options: {}".format(
                key, default_val, file_val, options_val
            ))
            if vals:
                options_val = (options_val in vals and options_val) or None
                file_val = (file_val in vals and file_val) or None
                env_val = (env_val in vals and env_val) or None
            if metadata.get("is_file"):
                filename = options_val or env_val
                if not filename:
                    self.config[key] = default_val
                else:
                    try:
                        with open(filename, 'r') as fh:
                            self.config[key] = fh.read()
                    except IOError:
                        debug("Could not open file {} for reading.".format(
                            filename)
                        )
                        self.config[key] = default_val
            else:
                set_values = [
                    val for val in (options_val, env_val, file_val)
                    if val is not None
                ]
                if len(set_values) > 0:
                    self.config[key] = set_values[0]
                else:
                    self.config[key] = default_val
            if metadata.get("type") and self.config[key]:
                debug("{} cast to {}".format(key, metadata.get("type")))
                self.config[key] = metadata.get("type")(self.config[key])
        debug(repr(self.config))

    def createAction(self, text, slot=None, shortcut=None, icon=None, tip=None,
                     checkable=False, signal="triggered"):
        """Return a QAction given a number of common QAction attributes

        Just a shortcut function Originally borrowed from
        'Rapid GUI Development with PyQT' by Mark Summerset
        """
        action = QAction(text, self)
        if icon is not None:
            action.setIcon(QIcon.fromTheme(
                icon, QIcon(":/{}.png".format(icon))
            ))
        if shortcut is not None and not shortcut.isEmpty():
            action.setShortcut(shortcut)
            tip += " ({})".format(shortcut.toString())
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None:
            action.__getattr__(signal).connect(slot)
        if checkable:
            action.setCheckable()
        return action

    def __init__(self, options, parent=None):
        """Construct a MainWindow Object."""
        super(MainWindow, self).__init__(parent)
        # Load config file
        self.setWindowTitle("Browser")
        debug("loading configuration from '{}'".format(options.config_file))
        configfile = {}
        if options.config_file:
            configfile = yaml.safe_load(open(options.config_file, 'r'))
        self.parse_config(configfile, options)
        # self.popup will hold a reference to the popup window
        # if it gets opened
        self.popup = None

        # Stylesheet support
        if self.config.get("stylesheet"):
            try:
                with open(self.config.get("stylesheet")) as ss:
                    self.setStyleSheet(ss.read())
            except:
                debug(
                    """Problem loading stylesheet file "{}", """
                    """using default style."""
                    .format(self.config.get("stylesheet"))
                )
        self.setObjectName("global")

        # If the whitelist is activated, add the bookmarks and start_url
        if self.config.get("whitelist"):
            # we can just specify whitelist = True,
            # which should whitelist just the start_url and bookmark urls.
            if type(self.config.get("whitelist")) is not list:
                self.whitelist = []
            self.whitelist.append(str(QUrl(
                self.config.get("start_url")
            ).host()))
            bookmarks = self.config.get("bookmarks")
            if bookmarks:
                self.whitelist += [
                    str(QUrl(b.get("url")).host())
                    for k, b in bookmarks.items()
                ]
                self.whitelist = set(self.whitelist)  # uniquify and optimize
            debug("Generated whitelist: " + str(self.whitelist))

        self.build_ui()

    # ## END OF CONSTRUCTOR ## #

    def build_ui(self):
        """Set up the user interface for the main window.

        Unlike the constructor, this method is re-run
        whenever the browser is "reset" by the user.
        """

        debug("build_ui")
        inactivity_timeout = self.config.get("timeout")
        quit_button_tooltip = (
            self.config.get("quit_button_mode") == 'close'
            and "Click here to quit the browser."
            or """Click here when you are done.
            It will clear your browsing history"""
            """ and return you to the start page.""")
        qb_mode_callbacks = {'close': self.close, 'reset': self.reset_browser}
        to_mode_callbacks = {'close': self.close,
                             'reset': self.reset_browser,
                             'screensaver': self.screensaver}
        self.screensaver_active = False

        # ##Start GUI configuration## #
        self.browser_window = WcgWebView(self.config)
        self.browser_window.setObjectName("web_content")

        if (
            self.config.get("icon_theme") is not None
            and QT_VERSION_STR > '4.6'
        ):
            QIcon.setThemeName(self.config.get("icon_theme"))
        self.setCentralWidget(self.browser_window)
        debug("loading {}".format(self.config.get("start_url")))
        self.browser_window.setUrl(QUrl(self.config.get("start_url")))
        if self.config.get("fullscreen"):
            self.showFullScreen()
        elif (
            self.config.get("window_size") and
            self.config.get("window_size").lower() == 'max'
        ):
            self.showMaximized()
        elif self.config.get("window_size"):
            size = re.match(r"(\d+)x(\d+)", self.config.get("window_size"))
            if size:
                width, height = size.groups()
                self.setFixedSize(int(width), int(height))
            else:
                debug('Ignoring invalid window size "{}"'.format(
                    self.config.get("window_size")
                ))

        # Set up the top navigation bar if it's configured to exist
        if self.config.get("navigation"):
            self.navigation_bar = QToolBar("Navigation")
            self.navigation_bar.setObjectName("navigation")
            self.addToolBar(Qt.TopToolBarArea, self.navigation_bar)
            self.navigation_bar.setMovable(False)
            self.navigation_bar.setFloatable(False)

            #  Standard navigation tools
            self.nav_items = {}
            self.nav_items["back"] = self.browser_window.pageAction(QWebPage.Back)
            self.nav_items["forward"] = self.browser_window.pageAction(QWebPage.Forward)
            self.nav_items["refresh"] = self.browser_window.pageAction(QWebPage.Reload)
            self.nav_items["stop"] = self.browser_window.pageAction(QWebPage.Stop)
            # The "I'm finished" button.
            self.nav_items["quit"] = self.createAction(
                self.config.get("quit_button_text"),
                qb_mode_callbacks.get(self.config.get("quit_button_mode"), self.reset_browser),
                QKeySequence("Alt+F"),
                None,
                quit_button_tooltip)
            # Zoom buttons
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
            if self.config.get("allow_printing"):
                self.nav_items["print"] = self.createAction(
                    "Print",
                    self.browser_window.print_webpage,
                    QKeySequence("Ctrl+p"),
                    "document-print",
                    "Print this page")

            # Add all the actions to the navigation bar.
            for item in self.config.get("navigation_layout"):
                if item == "separator":
                    self.navigation_bar.addSeparator()
                elif item == "spacer":
                    # an expanding spacer.
                    spacer = QWidget()
                    spacer.setSizePolicy(
                        QSizePolicy.Expanding, QSizePolicy.Preferred)
                    self.navigation_bar.addWidget(spacer)
                elif item == "bookmarks":
                    # Insert bookmarks buttons here.
                    self.bookmark_buttons = []
                    for bookmark in self.config.get("bookmarks", {}).items():
                        debug("Bookmark:\n" + bookmark.__str__())
                        # bookmark name will use the "name" attribute, if present
                        # or else just the key:
                        bookmark_name = bookmark[1].get("name") or bookmark[0]
                        # Create a button for the bookmark as a QAction,
                        # which we'll add to the toolbar
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

            # This removes the ability to toggle off the navigation bar:
            self.nav_toggle = self.navigation_bar.toggleViewAction()
            self.nav_toggle.setVisible(False)
            # End "if show_navigation is True" block

        # set hidden quit action
        # For reasons I haven't adequately ascertained,
        # this shortcut fails now and then claiming
        # "Ambiguous shortcut overload".
        # No idea why, as it isn't consistent.
        self.really_quit = self.createAction(
            "", self.close, QKeySequence("Ctrl+Alt+Q"), None, ""
        )
        self.addAction(self.really_quit)

        # Call a reset function after timeout
        if inactivity_timeout != 0:
            self.event_filter = InactivityFilter(inactivity_timeout)
            QCoreApplication.instance().installEventFilter(self.event_filter)
            self.browser_window.page().installEventFilter(self.event_filter)
            self.event_filter.timeout.connect(
                to_mode_callbacks.get(self.config.get("timeout_mode"),
                                      self.reset_browser))
        else:
            self.event_filter = None

        # ##END OF UI SETUP## #

    def screensaver(self):
        """Enter "screensaver" mode

        This method puts the browser in screensaver mode, where a URL
        is displayed while the browser is idle.  Activity causes the browser to
        return to the home screen.
        """
        debug("screensaver started")
        self.screensaver_active = True
        if self.popup:
            self.popup.close()
        if self.config.get("navigation"):
            self.navigation_bar.hide()
        self.browser_window.setZoomFactor(self.config.get("zoom_factor"))
        self.browser_window.load(QUrl(self.config.get("screensaver_url")))
        self.event_filter.timeout.disconnect()
        self.event_filter.activity.connect(self.reset_browser)

    def reset_browser(self):
        """Clear the history and reset the UI.

        Called whenever the inactivity filter times out,
        or when the user clicks the "finished" button in
        'reset' mode.
        """
        # Clear out the memory cache
        QWebSettings.clearMemoryCaches()
        self.browser_window.history().clear()
        # self.navigation_bar.clear() doesn't do its job,
        # so remove the toolbar first, then rebuild the UI.
        debug("RESET BROWSER")
        if self.event_filter:
            self.event_filter.blockSignals(True)
        if self.screensaver_active is True:
            self.screensaver_active = False
            self.event_filter.activity.disconnect()
        if self.event_filter:
            self.event_filter.blockSignals(False)
        if hasattr(self, "navigation_bar"):
            self.removeToolBar(self.navigation_bar)
        self.build_ui()

    def zoom_in(self):
        """Zoom in action callback.

        Note that we cap zooming in at a factor of 3x.
        """
        if self.browser_window.zoomFactor() < 3.0:
            self.browser_window.setZoomFactor(
                self.browser_window.zoomFactor() + 0.1
            )
            self.nav_items["zoom_out"].setEnabled(True)
        else:
            self.nav_items["zoom_in"].setEnabled(False)

    def zoom_out(self):
        """Zoom out action callback.

        Note that we cap zooming out at 0.1x.
        """
        if self.browser_window.zoomFactor() > 0.1:
            self.browser_window.setZoomFactor(
                self.browser_window.zoomFactor() - 0.1
            )
            self.nav_items["zoom_in"].setEnabled(True)
        else:
            self.nav_items["zoom_out"].setEnabled(False)


# ## END Main Application Window Class def ## #


class InactivityFilter(QTimer):
    """This defines an inactivity filter.

    It's basically a timer that resets when user "activity"
    (Mouse/Keyboard events) are detected in the main application.
    """
    activity = pyqtSignal()

    def __init__(self, timeout=0, parent=None):
        """Constructor for the class.

        args:
          timeout -- number of seconds before timer times out (integer)
        """
        super(InactivityFilter, self).__init__(parent)
        # timeout needs to be converted from seconds to milliseconds
        self.timeout_time = timeout * 1000
        self.setInterval(self.timeout_time)
        self.start()

    def eventFilter(self, object, event):
        """Overridden from QTimer.eventFilter"""
        if event.type() in (
            QEvent.MouseMove, QEvent.MouseButtonPress,
            QEvent.HoverMove, QEvent.KeyPress,
            QEvent.KeyRelease
        ):
            self.activity.emit()
            self.start(self.timeout_time)
            # commented this debug code,
            # because it spits out way to much information.
            # uncomment if you're having trouble with the timeout detecting
            # user inactivity correctly to determine what it's detecting
            # and ignoring:

            # debug ("Activity: %s type %d" % (event, event.type()))
            # else:
            # debug("Ignored event: %s type %d" % (event, event.type()))
        return QObject.eventFilter(self, object, event)


class WcgWebView(QWebView):
    """This is the webview for the application.

    It represents a browser window, either the main one or a popup.
    It's a simple wrapper around QWebView that configures some basic settings.
    """
    def __init__(self, config, parent=None, **kwargs):
        """Constructor for the class"""
        super(WcgWebView, self).__init__(parent)
        self.kwargs = kwargs
        self.config = config
        self.nam = (config.get('networkAccessManager')
                    or QNetworkAccessManager())
        self.setPage(WCGWebPage())
        self.page().user_agent = config.get('user_agent', None)
        self.page().setNetworkAccessManager(self.nam)
        self.page().force_js_confirm = config.get("force_js_confirm")
        self.settings().setAttribute(
            QWebSettings.JavascriptCanOpenWindows,
            config.get("allow_popups")
        )
        if config.get('user_css'):
            self.settings().setUserStyleSheetUrl(QUrl(config.get('user_css')))
        # JavascriptCanCloseWindows is in the API documentation,
        # but apparently only exists after 4.8
        if QT_VERSION_STR >= '4.8':
            self.settings().setAttribute(
                QWebSettings.JavascriptCanCloseWindows,
                config.get("allow_popups")
            )
        self.settings().setAttribute(
            QWebSettings.PrivateBrowsingEnabled,
            config.get("privacy_mode")
        )
        self.settings().setAttribute(QWebSettings.LocalStorageEnabled, True)
        self.settings().setAttribute(
            QWebSettings.PluginsEnabled,
            config.get("allow_plugins")
        )
        self.page().setForwardUnsupportedContent(
            config.get("allow_external_content")
        )
        self.setZoomFactor(config.get("zoom_factor"))

        # add printing to context menu if it's allowed
        if config.get("allow_printing"):
            self.print_action = QAction("Print", self)
            self.print_action.setIcon(QIcon.fromTheme("document-print"))
            self.print_action.triggered.connect(self.print_webpage)
            self.page().printRequested.connect(self.print_webpage)
            self.print_action.setToolTip("Print this web page")

        # Set up the proxy if there is one set
        if config.get("proxy_server"):
            if ":" in config["proxy_server"]:
                proxyhost, proxyport = config["proxy_server"].split(":")
            else:
                proxyhost = config["proxy_server"]
                proxyport = 8080
            self.nam.setProxy(QNetworkProxy(
                QNetworkProxy.HttpProxy, proxyhost, int(proxyport)
            ))

        # connections for wcgwebview
        self.page().networkAccessManager().authenticationRequired.connect(
            self.auth_dialog
        )
        self.page().unsupportedContent.connect(self.handle_unsupported_content)
        self.page().networkAccessManager().sslErrors.connect(
            self.sslErrorHandler
        )
        self.urlChanged.connect(self.onLinkClick)
        self.loadFinished.connect(self.onLoadFinished)

    def createWindow(self, type):
        """Handle requests for a new browser window.

        Method called whenever the browser requests a new window
        (e.g., <a target='_blank'> or window.open()).
        Overridden from QWebView to allow for popup windows, if enabled.
        """
        if self.config.get("allow_popups"):
            self.popup = WcgWebView(
                None,
                self.config,
                networkAccessManager=self.nam,
                **self.kwargs
            )
            # This assumes the window manager has an "X" icon
            # for closing the window somewhere to the right.
            self.popup.setObjectName("web_content")
            self.popup.setWindowTitle(
                "Click the 'X' to close this window! ---> "
            )
            self.popup.page().windowCloseRequested.connect(self.popup.close)
            self.popup.show()
            return self.popup
        else:
            debug("Popup not loaded on {}".format(self.url().toString()))

    def contextMenuEvent(self, event):
        """Handle requests for a context menu in the browser.

        Overridden from QWebView,
        to provide right-click functions according to user settings.
        """
        menu = QMenu(self)
        for action in [
                QWebPage.Back, QWebPage.Forward,
                QWebPage.Reload, QWebPage.Stop
        ]:
            action = self.pageAction(action)
            if action.isEnabled():
                menu.addAction(action)
        if self.config.get("allow_printing"):
            menu.addAction(self.print_action)
        menu.exec_(event.globalPos())

    def sslErrorHandler(self, reply, errorList):
        """Handle SSL errors in the browser.

        Overridden from QWebView.
        Called whenever the browser encounters an SSL error.
        Checks the ssl_mode and responds accordingly.
        """
        if self.config.get("ssl_mode") == 'ignore':
            reply.ignoreSslErrors()
            debug("SSL error ignored")
            debug(", ".join([str(error.errorString()) for error in errorList]))
        else:
            self.setHtml(
                CERTIFICATE_ERROR.format(
                    url=reply.url().toString(),
                    start_url=self.config.get("start_url")
                ))

    def auth_dialog(self, reply, authenticator):
        """Handle requests for HTTP authentication

        This is called when a page requests authentication.
        It might be nice to actually have a dialog here,
        but for now we just use the default credentials from the config file.
        """
        debug("Auth required on {}".format(reply.url().toString()))
        default_user = self.config.get("default_user")
        default_password = self.config.get("default_password")
        if (default_user):
            authenticator.setUser(default_user)
        if (default_password):
            authenticator.setPassword(default_password)

    def handle_unsupported_content(self, reply):
        """Handle requests to open non-web content

        Called basically when the reply from the request is not HTML
        or something else renderable by qwebview.  It checks the configured
        content-handlers for a matching MIME type, and opens the file or
        displays an error per the configuration.
        """
        self.reply = reply
        self.content_type = self.reply.header(
            QNetworkRequest.ContentTypeHeader).toString()
        self.content_filename = re.match(
            '.*;\s*filename=(.*);',
            self.reply.rawHeader('Content-Disposition')
        )
        self.content_filename = QUrl.fromPercentEncoding(
            (self.content_filename and self.content_filename.group(1))
            or ''
        )
        content_url = self.reply.url()
        debug(
            "Loading url {} of type {}".format(
                content_url.toString(), self.content_type
            ))
        if not self.config.get("content_handlers").get(str(self.content_type)):
            self.setHtml(UNKNOWN_CONTENT_TYPE.format(
                mime_type=self.content_type,
                file_name=self.content_filename,
                url=content_url.toString()))
        else:
            if str(self.url().toString()) in ('', 'about:blank'):
                self.setHtml(DOWNLOADING_MESSAGE.format(
                    filename=self.content_filename,
                    mime_type=self.content_type,
                    url=content_url.toString()))
            else:
                # print(self.url())
                self.load(self.url())
            self.reply.finished.connect(self.display_downloaded_content)

    def display_downloaded_content(self):
        """Open downloaded non-html content in a separate application.

        Called when an unsupported content type is finished downloading.
        """
        file_path = (
            QDir.toNativeSeparators(
                QDir.tempPath() + "/XXXXXX_" + self.content_filename
            )
        )
        myfile = QTemporaryFile(file_path)
        myfile.setAutoRemove(False)
        if myfile.open():
            myfile.write(self.reply.readAll())
            myfile.close()
            subprocess.Popen([
                (self.config.get("content_handlers")
                 .get(str(self.content_type))),
                myfile.fileName()
            ])

            # Sometimes downloading files opens an empty window.
            # So if the current window has no URL, close it.
            if(str(self.url().toString()) in ('', 'about:blank')):
                self.close()

    def onLinkClick(self, url):
        """Handle clicked hyperlinks.

        Overridden from QWebView.
        Called whenever the browser navigates to a URL;
        handles the whitelisting logic and does some debug logging.
        """
        debug("Request URL: {}".format(url.toString()))
        if not url.isEmpty():
            # If whitelisting is enabled, and this isn't the start_url host,
            # check the url to see if the host's domain matches.
            if (
                self.config.get("whitelist")
                and not (url.host() ==
                         QUrl(self.config.get("start_url")).host())
                and not str(url.toString()) == 'about:blank'
            ):
                site_ok = False
                pattern = re.compile(str("(^|.*\.)(" + "|".join(
                    [re.escape(w)
                     for w
                     in self.config.get("whitelist")]
                ) + ")$"))
                debug("Whitelist pattern: {}".format(pattern.pattern))
                if re.match(pattern, url.host()):
                    site_ok = True
                if not site_ok:
                    debug("Site violates whitelist: {}, {}".format(
                        url.host(), url.toString())
                    )
                    self.setHtml(self.config.get("page_unavailable_html")
                                 .format(**self.config))
            if not url.isValid():
                debug("Invalid URL {}".format(url.toString()))
            else:
                debug("Load URL {}".format(url.toString()))

    def onLoadFinished(self, ok):
        """Handle loadFinished events.

        Overridden from QWebView.
        This function is called when a page load finishes.
        We're checking to see if the load was successful;
        if it's not, we display either the 404 error (if
        it's just some random page), or a "network is down" message
        (if it's the start page that failed).
        """
        if not ok:
            if (
                self.url().host() == QUrl(self.config.get("start_url")).host()
                and str(self.url().path()).rstrip("/") ==
                    str(QUrl(self.config.get("start_url")).path()).rstrip("/")
            ):
                self.setHtml(self.config.get("network_down_html")
                             .format(**self.config), QUrl())
                debug("Start Url doesn't seem to be available;"
                      " displaying error")
            else:
                debug("404 on URL: {}" .format(self.url().toString()))
                self.setHtml(
                    self.config.get("page_unavailable_html")
                    .format(**self.config), QUrl()
                )
        return True

    def print_webpage(self):
        """Print the webpage to a printer.

        Callback for the print action.
        Should show a print dialog and print the webpage to the printer.
        """
        if self.print_settings.get("mode") == "high":
            printer = QPrinter(mode=QPrinter.HighResolution)
        else:
            printer = QPrinter(mode=QPrinter.ScreenResolution)

        if self.print_settings:
            if self.print_settings.get("size_unit"):
                try:
                    unit = getattr(
                        QPrinter,
                        self.print_settings.get("size_unit").capitalize()
                    )
                except NameError:
                    debug(
                        "Specified print size unit '{}' not found,"
                        "using default.".format(
                            self.print_settings.get("size_unit")
                        ))
                    unit = QPrinter.Millimeter
            else:
                unit = QPrinter.Millimeter

            margins = (
                list(self.print_settings.get("margins"))
                or list(printer.getPageMargins(unit))
            )
            margins += [unit]
            printer.setPageMargins(*margins)

            if self.print_settings.get("orientation") == "landscape":
                printer.setOrientation(QPrinter.Landscape)
            else:
                printer.setOrientation(QPrinter.Portrait)

            if self.print_settings.get("paper_size"):
                printer.setPaperSize(QSizeF(
                    *self.print_settings.get("paper_size")
                ), unit)

            if self.print_settings.get("resolution"):
                printer.setResolution(
                    int(self.print_settings.get("resolution"))
                )

        if not self.print_settings.get("silent"):
            print_dialog = QPrintDialog(printer, self)
            print_dialog.setWindowTitle("Print Page")
            if not print_dialog.exec_() == QDialog.Accepted:
                return False

        self.print_(printer)
        return True

# ### END WCGWEBVIEW DEFINITION ### #

# ### WCGWEBPAGE #### #


class WCGWebPage(QWebPage):
    """Subclassed QWebPage representing the actual web page object in the browser.

    This was subclassed so that some functions can be overridden.
    """
    def __init__(self, parent=None):
        """Constructor for the class"""
        super(WCGWebPage, self).__init__(parent)
        self.user_agent = None

    def javaScriptConsoleMessage(self, message, line, sourceid):
        """Handle console.log messages from javascript.

        Overridden from QWebPage so that we can
        send javascript errors to debug.
        """
        debug('Javascript Error in "{}" line {}: {}'.format(
            sourceid, line, message)
        )

    def javaScriptConfirm(self, frame, msg):
        """Handle javascript confirm() dialogs.

        Overridden from QWebPage so that we can (if configured)
        force yes/no on these dialogs.
        """
        if self.force_js_confirm == "accept":
            return True
        elif self.force_js_confirm == "deny":
            return False
        else:
            return QWebPage.javaScriptConfirm(self, frame, msg)

    def javaScriptAlert(self, frame, msg):
        if not self.suppress_alerts:
            return QWebPage.javaScriptAlert(self, frame, msg)

    def userAgentForUrl(self, url):
        """Handle reqests for the browser's user agent

        Overridden from QWebPage so we can force a user agent from the config.
        """
        return self.user_agent or QWebPage.userAgentForUrl(self, url)


# ### END WCGWEBPAGE DEFINITION ### #

# ######## Main application code begins here ################## #

if __name__ == "__main__":
    # Create the qapplication object,
    # so it can interpret the qt-specific CLI args
    app = QApplication(sys.argv)

    # locate the configuration file to use.
    if os.path.isfile(os.path.expanduser("~/.wcgbrowser.yaml")):
        default_config_file = os.path.expanduser("~/.wcgbrowser.yaml")
    elif os.path.isfile("/etc/wcgbrowser.yaml"):
        default_config_file = "/etc/wcgbrowser.yaml"
    else:
        default_config_file = None

    # Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(  # Start URL
        "-l", "--url", action="store", dest="start_url",
        help="Start browser at URL"
    )
    parser.add_argument(  # Full Screen
        "-f", "--fullscreen", action="store_true", default=argparse.SUPPRESS,
        dest="fullscreen", help="Start browser FullScreen"
    )
    parser.add_argument(  # No Navigation
        "-n", "--no-navigation", action="store_false", default=argparse.SUPPRESS,
        dest="navigation", help="Start browser without Navigation controls"
    )
    parser.add_argument(  # Config file
        "-c", "--config-file", action="store", default=default_config_file,
        dest="config_file", help="Specifiy an alternate config file"
    )
    parser.add_argument(  # Debug
        "-d", "--debug", action="store_true", default=False, dest="DEBUG",
        help="Enable debugging output to stdout"
    )
    parser.add_argument(  # Debug Log
        "--debug_log", action="store", default=None, dest="debug_log",
        help="Enable debug output to the specified filename"
    )
    parser.add_argument(  # Timeout
        "-t", "--timeout", action="store", type=int, default=argparse.SUPPRESS,
        dest="timeout",
        help="Define the timeout in seconds after which to reset the browser"
        "due to user inactivity"
    )
    parser.add_argument(  # icon theme
        "-i", "--icon-theme", action="store", default=None, dest="icon_theme",
        help="override default icon theme with other Qt/KDE icon theme"
    )
    parser.add_argument(  # Default zoom factor
        "-z", "--zoom", action="store", type=float, default=argparse.SUPPRESS,
        dest="zoomfactor", help="Set the zoom factor for web pages"
    )
    parser.add_argument(  # Allow popups
        "-p", "--popups", action="store_true", default=argparse.SUPPRESS,
        dest="allow_popups", help="Allow the browser to open new windows"
    )
    parser.add_argument(  # Default HTTP user
        "-u", "--user", action="store", dest="default_user",
        help="Set the default username used for URLs"
        " that require authentication"
    )
    parser.add_argument(  # Default HTTP password
        "-w", "--password", action="store", dest="default_password",
        help="Set the default password used for URLs"
        " that require authentication"
    )
    parser.add_argument(  # Allow launching of external programs
        "-e", "--allow_external", action="store_true", default=argparse.SUPPRESS,
        dest='allow_external_content',
        help="Allow the browser to open content in external programs."
    )
    parser.add_argument(  # Allow browser plugins
        "-g", "--allow_plugins", action="store_true", default=argparse.SUPPRESS,
        dest='allow_plugins',
        help="Allow the browser to use plugins like"
        " Flash or Java (if installed)"
    )
    parser.add_argument(  # Window size
        "--size", action="store", dest="window_size", default=None,
        help="Specify the default window size in pixels (widthxheight),"
        " or 'max' to maximize"
    )
    parser.add_argument(  # HTTP Proxy server
        "--proxy_server", action="store", dest="proxy_server", default=None,
        help="Specify a proxy server string, in the form host:port"
    )

    # rather than parse sys.argv here, we're parsing app.arguments
    # so that qt-specific args are removed.
    # we also need to remove argument 0.
    args = parser.parse_args([str(x) for x in list(app.arguments())][1:])
    DEBUG = args.DEBUG
    DEBUG_LOG = args.debug_log
    if not args.config_file:
        debug("No config file found or specified; using defaults.")

    # run the actual application
    mainwin = MainWindow(args)
    mainwin.show()
    app.exec_()
