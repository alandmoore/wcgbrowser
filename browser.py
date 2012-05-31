#!/usr/bin/python
from PyQt4.QtGui import QMainWindow, QAction, QIcon, QWidget, QApplication, QSizePolicy, QKeySequence, QToolBar 
from PyQt4.QtCore import QUrl, SIGNAL, QTimer, QObject, QT_VERSION_STR, QEvent, Qt
from PyQt4.QtWebKit import QWebView, QWebPage, QWebSettings

import sys
import os
import argparse
#rom configobj import ConfigObj
import yaml

class MainWindow(QMainWindow):
    def createAction(self, text, slot=None, shortcut=None, icon=None, tip=None, checkable=False, signal="triggered()"):
        """Borrowed from 'Rapid GUI Development with PyQT by Mark Summerset'"""
        action = QAction(text, self)
        if icon is not None:
            action .setIcon(QIcon.fromTheme(icon, QIcon(":/%s.png" % icon)))
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

    def onLinkClick(self, url):
        if DEBUG:
            if not url.isValid():
                print("Invalid URL %s" % url)
            else:
                print("Load URL %s" %url)
                               
    def __init__(self, options, parent = None):
        super(MainWindow, self).__init__(parent)
        #Load config file
        self.options = options
        self.configuration = yaml.safe_load(open(self.options.config_file, 'r'))
        if DEBUG:
            print("loading configuration from '%s'" % options.config_file)
            print(self.configuration)
        self.build_ui(self.options, self.configuration)
        self.html404 = """<h2>Unavailable</h2>
        <p>You have attempted to navigate to a page which is not accessible from this terminal.</p>
        <p><a href='%s'>Click here</a> to return to the start page.</p> """ % (self.startUrl)
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
        self.icon_theme = options.icon_theme or configuration.get("icon_theme", None)
        self.zoomfactor = options.zoomfactor or float(configuration.get("zoom_factor") or 1.0)
        self.allowPopups = options.allowPopups or configuration.get("allow_popups", False) 
        self.isFullscreen = options.isFullscreen or configuration.get("fullscreen", False) 
        self.showNavigation = not options.noNav and configuration.get('navigation', True)
        
        ###Start GUI configuration###
        self.browserWindow = WcgWebView(allowPopups=self.allowPopups)
        self.browserWindow.settings().setAttribute(QWebSettings.JavascriptCanOpenWindows, self.allowPopups)
        #JavascriptCanCloseWindows is in the API documentation, but my system claims QWebSettings has no such member.
        #self.browserWindow.settings().setAttribute(QWebSettings.JavascriptCanCloseWindows, self.allowPopups)
        self.browserWindow.settings().setAttribute(QWebSettings.PrivateBrowsingEnabled, True)
        self.browserWindow.settings().setAttribute(QWebSettings.PluginsEnabled, False)
        self.browserWindow.setZoomFactor(self.zoomfactor)
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
        if self.showNavigation is True:
            self.navigationBar = QToolBar("Navigation")
            self.addToolBar(Qt.TopToolBarArea, self.navigationBar)
            self.navigationBar.setMovable(False)
            self.navigationBar.setFloatable(False)
            self.back = self.browserWindow.pageAction(QWebPage.Back)
            self.forward = self.browserWindow.pageAction(QWebPage.Forward)
            self.refresh = self.browserWindow.pageAction(QWebPage.Reload)
            self.stop = self.browserWindow.pageAction(QWebPage.Stop)
            self.quit = self.createAction("I'm &Finished", self.reset_browser, QKeySequence("Alt+F"), None, "Click here when you are done to clear your browsing history and reset the search.")
            self.zoom_in_button = self.createAction("Zoom In", self.zoom_in, QKeySequence("Alt++"), "zoom-in", "Increase the size of the text and images on the page")
            self.zoom_out_button = self.createAction("Zoom Out", self.zoom_out, QKeySequence("Alt+-"), "zoom-out", "Decrease the size of text and images on the page")
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
                        print("%s, %s, %s\n" % (bookmark[0], bookmark[1]["url"], bookmark[1]["description"]))
                    button = self.createAction(bookmark[0],
                                           lambda url=bookmark[1].get("url"): self.browserWindow.load(QUrl(url)),
                                           QKeySequence.mnemonic(bookmark[0]),
                                           None,
                                           bookmark[1].get("description")
                                           )
                    self.navigationBar.addAction(button)
                self.navigationBar.addSeparator()
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.navigationBar.addWidget(spacer)
            self.navigationBar.addAction(self.quit)
            
            #This removes the ability to toggle off the navigation bar:
            self.navToggle = self.navigationBar.toggleViewAction()
            self.navToggle.setVisible(False)
            #End "if showNavigation is True" block

        #set hidden quit action    
        self.really_quit = self.createAction("", self.close, QKeySequence("Ctrl+Alt+Shift+Q"), None, "")
        self.addAction(self.really_quit)

        #Call a reset function after timeout
        if inactivity_timeout != 0:
            self.ef = Inactivity_Filter(inactivity_timeout)
            self.installEventFilter(self.ef)
            self.browserWindow.page().installEventFilter(self.ef)
            self.connect(self.ef, SIGNAL("timeout()"), self.reset_browser)

        
        ###CONNECTIONS### 
        self.connect (self.browserWindow, SIGNAL("urlChanged(QUrl)"), self.onLinkClick)
        self.connect (self.browserWindow.page().networkAccessManager(), SIGNAL("sslErrors (QNetworkReply *, const QList<QSslError> &)"), self.sslErrorHandler)
        self.connect (self.browserWindow, SIGNAL("loadFinished(bool)"), self.onLoadFinished)

        ###END OF CONSTRUCTOR###

    def reset_browser(self):
        # self.navigationBar.clear() doesn't do its job, so remove the toolbar first, then rebuild the UI.
        self.removeToolBar(self.navigationBar)
        self.build_ui(self.options, self.configuration)


    def sslErrorHandler(self, reply, errorList):
        reply.ignoreSslErrors()
        if DEBUG:
            print ("SSL error ignored")
            for error in errorList:
                print(error.errorString())

    def onLoadFinished(self, ok):
        if not ok:
            if self.browserWindow.url().host() == QUrl(self.startUrl).host():
                self.browserWindow.setHtml(self.htmlNetworkDown, QUrl())
            else:
                print (self.browserWindow.url().toString() + " = " + self.startUrl)
                self.browserWindow.setHtml(self.html404, QUrl())
        return True

    def zoom_in(self):
        if self.browserWindow.zoomFactor() < 3.0:
            self.browserWindow.setZoomFactor(self.browserWindow.zoomFactor() + 0.1)
            self.zoom_out_button.setEnabled(True)
        else:
            self.zoom_in_button.setEnabled(False)
            
    def zoom_out(self):
        if self.browserWindow.zoomFactor() > 0.1:
            self.browserWindow.setZoomFactor(self.browserWindow.zoomFactor() - 0.1)
            self.zoom_in_button.setEnabled(True)
        else:
            self.zoom_out_button.setEnabled(False)
            
class Inactivity_Filter(QTimer):
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
    def __init__(self, parent=None, **kwargs):
        super(WcgWebView, self).__init__(parent)
        self.allowPopups = kwargs.get('allowPopups')
    def createWindow(self, type):
        if self.allowPopups:
            self.popup = WcgWebView(None, allowPopups=self.allowPopups)
            return self.popup
        else:
            if DEBUG:
                print ("Popup not loaded on %s" % self.url().toString())




######### Main application code begins here ###################

def main(args):
    app = QApplication(sys.argv)
    mainwin = MainWindow(args)
    mainwin.show()
    app.exec_()


if __name__ == "__main__":
    if os.path.isfile(os.path.expanduser("~/.wcgbrowser.yaml")):
        default_config_file =  os.path.expanduser("~/.wcgbrowser.yaml")
    elif os.path.isfile("/etc/wcgbrowser.yaml"):
        default_config_file = "/etc/wcgbrowser.yaml"
    else:
        default_config_file = None
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--url", action="store", dest="url", help="start browser at URL")
    parser.add_argument("-f", "--fullscreen", action="store_true", default=False, dest="isFullscreen", help="start browser FullScreen")
    parser.add_argument("-n", "--no-navigation", action="store_true", default=False, dest="noNav", help="start browser without Navigation controls")
    parser.add_argument("-c", "--config-file", action="store", default=default_config_file, dest="config_file", help="Specifiy an alternate config file")
    parser.add_argument("-d", "--debug", action="store_true", default=False, dest="DEBUG", help="enable debugging output")
    parser.add_argument("-t", "--timeout", action="store", type=int,  default=0, dest="timeout", help="define the timeout in seconds after which to reset the browser due to user inactivity")
    parser.add_argument("-i", "--icon-theme", action="store", default=None, dest="icon_theme", help="override default icon theme with other Qt/KDE icon theme")
    parser.add_argument("-z", "--zoom", action="store", type=float, default=0, dest="zoomfactor", help="set the zoom factor for web pages")
    parser.add_argument("-p", "--popups", action="store_true", default=False, dest="allowPopups", help="allow the browser to open new windows")
    args = parser.parse_args()
    if not args.config_file:
        print ("No config file found or specified; using defaults.")
    DEBUG = args.DEBUG
    main(args)


