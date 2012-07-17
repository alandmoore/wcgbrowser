#!/usr/bin/python
# This is the main script for WCGBrowser, a kiosk-oriented web browser
# Written by Alan D Moore, http://www.alandmoore.com
# Released under the GNU GPL v3


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

class MainWindow(QMainWindow):
    """This class is the main application class, it defines the GUI window for the browser"""
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

                               
    def __init__(self, options, parent = None):
        super(MainWindow, self).__init__(parent)
        #Load config file
        self.options = options
        self.configuration = {}
        if self.options.config_file:
            self.configuration = yaml.safe_load(open(self.options.config_file, 'r'))
        self.defaultUser = options.default_user or  self.configuration.get("default_user")
        self.defaultPassword = options.default_password or self.configuration.get("default_password")
        
        if DEBUG:
            print("loading configuration from '%s'" % options.config_file)
            print(self.configuration)
        self.build_ui(self.options, self.configuration)

        #The following variable sets the error code when a page cannot be reached, either because of a generic 404, or because you've blocked it.
        self.html404 = """<h2>Unavailable</h2>
        <p>You have attempted to navigate to a page which is not accessible from this terminal.</p>
        <p><a href='%s'>Click here</a> to return to the start page.</p> """ % (self.startUrl)
        
        #This string is shown when sites that should be reachable (e.g. the start page) aren't.  You might want to put in contact information for your tech support, etc.
        self.htmlNetworkDown = """<h2>Network Error</h2><p>The start page, %s, cannot be reached.  This indicates a network connectivity problem.</p>
        <p>Staff, please check the following:</p>
        <ul>
        <li>Ensure the network connections at the computer and at the switch, hub, or wall panel are secure</li>
        <li>Restart the computer</li>
        <li>Ensure other systems at your location can access the same URL</li>
        </ul>
        <p>If you continue to get this error, contact technical support</p> """ % (self.startUrl)

    def build_ui(self, options, configuration):
        self.startUrl = options.url or configuration.get("start_url", "about:blank") 
        inactivity_timeout = options.timeout or int(configuration.get("timeout", 0))
        timeout_mode = configuration.get('timeout_mode', 'reset')
        self.icon_theme = options.icon_theme or configuration.get("icon_theme", None)
        self.zoomfactor = options.zoomfactor or float(configuration.get("zoom_factor") or 1.0)
        self.allowPopups = options.allowPopups or configuration.get("allow_popups", False) 
        self.isFullscreen = options.isFullscreen or configuration.get("fullscreen", False) 
        self.showNavigation = not options.noNav and configuration.get('navigation', True)
        self.content_handlers = self.configuration.get("content_handlers", {})
        self.allow_external_content = options.allow_external_content or self.configuration.get("allow_external_content", False)
        self.quit_button_mode = self.configuration.get("quit_button_mode", 'reset')
        self.quit_button_text = self.configuration.get("quit_button_text", "I'm &Finished")

        qb_mode_callbacks = {'close':self.close, 'reset':self.reset_browser}
    
        ###Start GUI configuration###
        self.browserWindow = WcgWebView(allowPopups=self.allowPopups, defaultUser = self.defaultUser, defaultPassword=self.defaultPassword, zoomfactor=self.zoomfactor, content_handlers=self.content_handlers, allow_external_content = self.allow_external_content)


        #Supposedly this code will make certificates work, but I could never
        #get it to work right.  For now we're just ignoring them.

        ## config = QSslConfiguration.defaultConfiguration()
        ## certs = config.caCertificates()
        ## certs.append(QSslCertificate(QFile("somecert.crt")))
        ## config.setCaCertificates(certs)
      
        if self.icon_theme is not None and QT_VERSION_STR > '4.6':
            QIcon.setThemeName(self.icon_theme)
        self.setCentralWidget(self.browserWindow)
        if DEBUG:
            print (options)
            print ("loading %s" % self.startUrl)
        self.browserWindow.setUrl(QUrl(self.startUrl))
        if self.isFullscreen is True:
            self.showFullScreen()

        #Set up the top navigation bar if it's configured to exist    
        if self.showNavigation is True:
            self.navigationBar = QToolBar("Navigation")
            self.addToolBar(Qt.TopToolBarArea, self.navigationBar)
            self.navigationBar.setMovable(False)
            self.navigationBar.setFloatable(False)

            #Standard navigation tools
            self.back = self.browserWindow.pageAction(QWebPage.Back)
            self.forward = self.browserWindow.pageAction(QWebPage.Forward)
            self.refresh = self.browserWindow.pageAction(QWebPage.Reload)
            self.stop = self.browserWindow.pageAction(QWebPage.Stop)
            #The "I'm finished" button.
            self.quit = self.createAction(
                self.quit_button_text,
                qb_mode_callbacks.get(self.quit_button_mode, self.reset_browser),
                QKeySequence("Alt+F"),
                None,
                "Click here when you are done. \nIt will clear your browsing history and return you to the start page."
                )
            #Zoom buttons
            self.zoom_in_button = self.createAction("Zoom In", self.zoom_in, QKeySequence("Alt++"), "zoom-in", "Increase the size of the text and images on the page")
            self.zoom_out_button = self.createAction("Zoom Out", self.zoom_out, QKeySequence("Alt+-"), "zoom-out", "Decrease the size of text and images on the page")

            #Add all the actions to the navigation bar.
            self.navigationBar.addAction(self.back)
            self.navigationBar.addAction(self.forward)
            self.navigationBar.addAction(self.refresh)
            self.navigationBar.addAction(self.stop)
            self.navigationBar.addAction(self.zoom_in_button)
            self.navigationBar.addAction(self.zoom_out_button)
            
            self.navigationBar.addSeparator()
            #Insert bookmarks buttons here.
            self.bookmark_buttons = []
            if configuration.get("bookmarks"):
                for bookmark in configuration.get("bookmarks").items():
                    if DEBUG:
                        print("Bookmark:\n" + bookmark.__str__())
                        
                    #Create a button for the bookmark as a QAction, which we'll add to the toolbar
                    button = self.createAction(bookmark[0],
                                           lambda url=bookmark[1].get("url"): self.browserWindow.load(QUrl(url)),
                                           QKeySequence.mnemonic(bookmark[0]),
                                           None,
                                           bookmark[1].get("description")
                                           )
                    self.navigationBar.addAction(button)
                self.navigationBar.addSeparator()
                
            #insert an expanding spacer to push the finish button all the way to the right.
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.navigationBar.addWidget(spacer)

            #add the finish button
            self.navigationBar.addAction(self.quit)
            
            #This removes the ability to toggle off the navigation bar:
            self.navToggle = self.navigationBar.toggleViewAction()
            self.navToggle.setVisible(False)
            #End "if showNavigation is True" block

        # set hidden quit action
        # For reasons I haven't adequately ascertained, this shortcut fails now and then claiming "Ambiguous shortcut overload".  No idea why, as it isn't consistent.
        self.really_quit = self.createAction("", self.close, QKeySequence("Ctrl+Alt+Q"), None, "")
        self.addAction(self.really_quit)

        #Call a reset function after timeout
        if inactivity_timeout != 0:
            self.ef = Inactivity_Filter(inactivity_timeout)
            self.installEventFilter(self.ef)
            self.browserWindow.page().installEventFilter(self.ef)
            self.connect(self.ef, SIGNAL("timeout()"), qb_mode_callbacks.get(timeout_mode, self.reset_browser))

        
        ###CONNECTIONS### 
        self.connect (self.browserWindow, SIGNAL("loadFinished(bool)"), self.onLoadFinished)
        ###END OF CONSTRUCTOR###

        

    def reset_browser(self):
        # self.navigationBar.clear() doesn't do its job, so remove the toolbar first, then rebuild the UI.
        self.removeToolBar(self.navigationBar)
        self.build_ui(self.options, self.configuration)


    def onLoadFinished(self, ok):
        """This function is called when a page load finishes.  We're checking to see if the load was successful; if it's not, we display either the 404 error, or a "network is down" message if it's the start page that failed or some random page."""
        if not ok:
            if self.browserWindow.url().host() == QUrl(self.startUrl).host():
                self.browserWindow.setHtml(self.htmlNetworkDown, QUrl())
            else:
                print (self.browserWindow.url().toString() + " = " + self.startUrl)
                self.browserWindow.setHtml(self.html404, QUrl())
        return True

    def zoom_in(self):
        """This is the callback for the zoom in action.  Note that we cap zooming in at a factor of 3x."""
        if self.browserWindow.zoomFactor() < 3.0:
            self.browserWindow.setZoomFactor(self.browserWindow.zoomFactor() + 0.1)
            self.zoom_out_button.setEnabled(True)
        else:
            self.zoom_in_button.setEnabled(False)
            
    def zoom_out(self):
        """This is the callback for the zoom out action.  Note that we cap zooming out at 0.1x."""
        if self.browserWindow.zoomFactor() > 0.1:
            self.browserWindow.setZoomFactor(self.browserWindow.zoomFactor() - 0.1)
            self.zoom_in_button.setEnabled(True)
        else:
            self.zoom_out_button.setEnabled(False)
            
class Inactivity_Filter(QTimer):
    """This class defines an inactivity filter, which is basically a timer that resets every time "activity" events are detected in the main application."""
    def __init__(self, timeout=0, parent=None):
        super(QTimer, self).__init__(parent)
        self.timeout = timeout * 1000 #timeout needs to be converted from seconds to milliseconds
        self.setInterval(self.timeout)
        self.start()
        
    def eventFilter(self, object,  event):
        if event.type() in (QEvent.HoverMove, QEvent.KeyPress, QEvent.KeyRelease, ):
            self.emit(SIGNAL("activity"))
            self.start(self.timeout)
            #commented this debug code, because it spits out way to much information.
            #uncomment if you're having trouble with the timeout detecting user inactivity correctly to determine what it's detecting and ignoring
            #if DEBUG:
            #    print ("Activity: %s type %d" % (event, event.type()))
        #else:
            #if DEBUG:
            #    print ("Ignored event: %s type %d" % (event, event.type()))
        return QObject.eventFilter(self, object, event)

class WcgWebView(QWebView):
    """This is the webview for the application.  It's a simple wrapper around QWebView that configures some basic settings."""
    def __init__(self, parent=None, **kwargs):
        super(WcgWebView, self).__init__(parent)
        self.kwargs = kwargs
        self.nam = kwargs.get('networkAccessManager') or QNetworkAccessManager()
        self.page().setNetworkAccessManager(self.nam)
        self.allowPopups = kwargs.get('allowPopups')
        self.defaultUser = kwargs.get('defaultUser', '')
        self.defaultPassword = kwargs.get('defaultPassword', '')
        self.settings().setAttribute(QWebSettings.JavascriptCanOpenWindows, self.allowPopups)
        #JavascriptCanCloseWindows is in the API documentation, but my system claims QWebSettings has no such member.
        #self.settings().setAttribute(QWebSettings.JavascriptCanCloseWindows, self.allowPopups)
        self.settings().setAttribute(QWebSettings.PrivateBrowsingEnabled, True)
        self.settings().setAttribute(QWebSettings.PluginsEnabled, False)
        self.zoomfactor = kwargs.get("zoomfactor", 1)
        self.allow_external_content = kwargs.get('allow_external_content')
        self.page().setForwardUnsupportedContent(self.allow_external_content)
        self.content_handlers = kwargs.get("content_handlers", {})
        self.setZoomFactor(self.zoomfactor)

        #connections for wcgwebview
        self.connect (self.page().networkAccessManager(), SIGNAL("authenticationRequired(QNetworkReply * , QAuthenticator *)"), self.auth_dialog)
        self.connect(self.page(), SIGNAL("unsupportedContent(QNetworkReply *)"), self.handle_unsupported_content)
        self.connect (self.page().networkAccessManager(), SIGNAL("sslErrors (QNetworkReply *, const QList<QSslError> &)"), self.sslErrorHandler)
        self.connect (self, SIGNAL("urlChanged(QUrl)"), self.onLinkClick)

    def createWindow(self, type):
        """This function has been overridden to allow for popup windows, if that feature is enabled."""
        if self.allowPopups:
            self.popup = WcgWebView(None, networkAccessManager=self.nam, **self.kwargs)
            #This assumes the window manager has an "X" icon for closing the window somewhere to the right.
            self.popup.setWindowTitle("Click the 'X' to close this window! ---> ")
            self.popup.show()
            return self.popup
        else:
            if DEBUG:
                print ("Popup not loaded on %s" % self.url().toString())

    #sslErrorHandler was overridden to ignore SSL errors, because I couldn't make certificates work.
    #Obviously, if you're in an environment where this could be a security risk, this is bad.
    def sslErrorHandler(self, reply, errorList):
        reply.ignoreSslErrors()
        if DEBUG:
            print ("SSL error ignored")
            for error in errorList:
                print(error.errorString())

    def auth_dialog(self, reply, authenticator):
        """This is called when a page requests authentication.  It might be nice to actually have a dialog here, but for now we just use the default credentials from the config file."""
        authenticator.setUser(self.defaultUser)
        authenticator.setPassword(self.defaultPassword)

    def handle_unsupported_content(self, reply):
        """Called basically when the reply from the request is not HTML or something else renderable by qwebview"""
        self.reply = reply
        self.content_type = self.reply.header(QNetworkRequest.ContentTypeHeader).toString()
        self.content_filename = re.match('.*;\s*filename=(.*);', self.reply.rawHeader('Content-Disposition'))
        self.content_filename =QUrl.fromPercentEncoding((self.content_filename and self.content_filename.group(1)) or '')
        content_url = self.reply.url()
        if DEBUG:
            print("Loading url %s of type %s" % (content_url.toString(), self.content_type))
        if not self.content_handlers.get(str(self.content_type)):
            self.setHtml("<h1>Failed: unrenderable content</h1><p>The browser does not know how to handle the content type <strong>%s</strong> of the file <strong>%s</strong> supplied by <strong>%s</strong>.</p>" % (self.content_type,  self.content_filename,  content_url.toString()))
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
        """This function is overridden strictly for debugging purposes"""
        if DEBUG:
            if not url.isValid():
                print("Invalid URL %s" % url.toString())
            else:
                print("Load URL %s" %url.toString())

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
        default_config_file =  os.path.expanduser("~/.wcgbrowser.yaml")
    elif os.path.isfile("/etc/wcgbrowser.yaml"):
        default_config_file = "/etc/wcgbrowser.yaml"
    else:
        default_config_file = None

    #Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--url", action="store", dest="url", help="Start browser at URL")
    parser.add_argument("-f", "--fullscreen", action="store_true", default=False, dest="isFullscreen", help="Start browser FullScreen")
    parser.add_argument("-n", "--no-navigation", action="store_true", default=False, dest="noNav", help="Start browser without Navigation controls")
    parser.add_argument("-c", "--config-file", action="store", default=default_config_file, dest="config_file", help="Specifiy an alternate config file")
    parser.add_argument("-d", "--debug", action="store_true", default=False, dest="DEBUG", help="Enable debugging output")
    parser.add_argument("-t", "--timeout", action="store", type=int,  default=0, dest="timeout", help="Define the timeout in seconds after which to reset the browser due to user inactivity")
    parser.add_argument("-i", "--icon-theme", action="store", default=None, dest="icon_theme", help="override default icon theme with other Qt/KDE icon theme")
    parser.add_argument("-z", "--zoom", action="store", type=float, default=0, dest="zoomfactor", help="Set the zoom factor for web pages")
    parser.add_argument("-p", "--popups", action="store_true", default=False, dest="allowPopups", help="Allow the browser to open new windows")
    parser.add_argument("-u", "--user", action="store", dest="default_user", help="Set the default username used for URLs that require authentication")
    parser.add_argument("-w", "--password", action="store", dest="default_password", help="Set the default password used for URLs that require authentication")
    parser.add_argument("-e", "--allow_external", action="store_true", default=False, dest='allow_external_content', help="Allow the browser to open content in external programs.")
    args = parser.parse_args()
    if not args.config_file:
        print ("No config file found or specified; using defaults.")
    DEBUG = args.DEBUG

    #run the actual application
    main(args)


