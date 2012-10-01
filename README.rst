============
 WCGBrowser
============

Author:  Alan D Moore (http://www.alandmoore.com, e-mail me_AT_alandmoore_DOT_com)


Description
===========

WCGBrowser is a browser I wrote specifically for use on web kiosks.  It's based on pyqt and webkit, and is designed to make lock-down very simple and painless.

It was originally conceived for use in library catalog terminals, when it became clear that browsers with ever-growing feature lists like Firefox and Chrome were too much work to lock down correctly and completely.  It was also designed to be easily configurable using a simple text file that can be hand-edited in a terminal over ssh across a slow WAN, so no databases, XML, or crazy binaries here.

Features
========

- Up-to-date webkit rendering
- Text-based, YAML configuration
- (Optional) Inactivity timeout
- Popups/open-in-new-window can be disabled
- Minimal, no-clutter interface simple for the general public.
- Configurable navigation bar with bookmarks
- Configurable handling of external MIME-types (PDF, etc)
- (Optional) Whitelisting of hosts & domains

Requirements
============

- Python 2.6 or higher (should work with python 3.x)
- PyQT4, preferably 4.6 or higher
- Python YAML library (http://pyyaml.org)
- Python argparse library

It should work on any platform, but it's only been tested on Debian (Squeeze) and Ubuntu (Lucid Lynx or higher)


Usage
=====

The included wcgbrowser.yaml file shows an actual configuration that I use at our public library system.  To use it,  copy it to /etc/wcgbrowser.yaml, ~/.wcgbrowser.yaml, or specify it with the -c (--config-file) switch.  You can make the browser.py executable, or launch it using python, like so::

    python browser.py

The --help switch should give you an up-to-date summary of the available command-line switches, but here are a few important ones:

====================    =====================================================================================================================================
 Switch                 Description
====================    =====================================================================================================================================
-l, --url               The "start location" for the browser.  This is the initial URL it will load, and where it will return when reset.
-f, --fullscreen        Makes the window fill the screen, no window decorations
-n, --no-navigation     Turn off the navigation panel (back, forward, home, shortcuts, etc).  Make sure your actual web application is fully navigable!
-c, --config-file       Specify a configuration file to use
-d, --debug             Provide debugging output to stdout
--debug_log             Send debugging output to specified file
-t, --timeout           The timeout for the inactivity monitor.  After this many seconds of inactivity, reset the browser
-i, --icon-theme        The icon theme to use.  You'll need to install these themes yourself
-z, --zoom              The default zoom factor for content.  0 ignores this.  1 is default, 2 would be double size, 0.5 would be half-size, etc.
-p, --popups            Enable the creation of new windows when a link is clicked that opens in a new window, or javascript tries to open a window
-u, --user	        Set the default username to be sent when a site requests authentication
-w, --password	        Set the default password to be sent when a site requests authentication
-e, --allow_external    Allow the browser to open content in external programs via MIME type
-g, --allow_plugins     Allow the use of plugins like Flash, Java, etc.
--size
====================    =====================================================================================================================================


Configuration File
==================

The sample configuration file is fully commented, and should be pretty easy to configure if you just read through it.  In case you just want to start from scratch, here are the current configuration options available for the application.

====================== ===============    ===============================================================================================================================================================================================================================================================
Option Name            Default Value      Explanation
====================== ===============    ===============================================================================================================================================================================================================================================================
start_url              about:blank        The starting URL or "home page"
default_user           (empty)            default username to send when pages request authentication
default_password       (empty)            default password to send when pages request authentication
timeout                0                  Number of seconds of inactivity before the browser closes or resets itself. A value of 0 disables the feature.
timeout_mode           reset              The action performed on inactivity timeout.  Values can be "reset" (to return to the start URL and clear history) or "close" (to close the program)
zoom_factor            1.0                The amount of zoom applied to pages.  .5 is half size, 2.0 is double size, etc.
allow_popups           False              Whether or not to allow navigation that requires opening a new browser window, such as javascript "window.open()" calls or links with a target of "_blank".  If False, the navigation will be ignored.  If true, a new window will be created as expected.
ssl_mode               strict             Defines how the browser handles ssl certificate errors.  "strict" will just give an error and prevent access to the problematic URL.  "ignore" will silently ignore the errors and allow access.
navigation             True               Display the navigation bar at the top (back/forward/reload/bookmarks/quit)
icon_theme             (qt4 default)      Icon theme to use for navigation icons
quit_button_text       "I'm &Finished"    Text to display on the quit/reset button.  Can include an accelerator indicator (&).
quit_button_mode       reset              Just like timeout_mode, only this is the action taken when the quit button is pressed (same options)
allow_external_content False              Whether or not to allow non-html content, e.g. PDF files.  If this is true, you need to specify a content handler for the MIME type or a 404 error, "Network Error", or blank page will likely be displayed to the user.
navigation_layout      (see below)        Sets the layout of the navigation bar.  See the detailed explanation below.
allow_plugins          False              If true, enables the use of plugins like flash, java, etc.
window_size            (empty)            If set, and if fullscreen is //not// set, make the window default to this size.  Can be <width>x<height> (e.g. 800x600) or 'max' for maximized.
whitelist              (empty)            A list of web domains or hosts to allow access to (see below).
====================== ===============    ===============================================================================================================================================================================================================================================================

Bookmarks
---------

Bookmarks are created in a YAML list called "bookmarks" with this format::

    bookmarks:
      "Bookmark Name":
       url: "http://bookmark.url/"
       description: "A short description of the bookmark, for the tooltip"

     "Another bookmark name":
      url: "http://example.com/some_bookmark"
      description: "A short description of this bookmark"

Bookmark names can include an ampersand to specify an accelerator key.


Content Handlers
----------------

If you're allowing external content to be launched, the "content_handlers" array allows you to specify in which programs the external content will open by MIME type.
The syntax looks like this::

    content_handlers:
      "application/pdf": "xpdf"
      "application/vnd.oasis.opendocument.text":"libreoffice"

WCGBrowser will download the file to a temp directory and pass it as an argument to whatever command you specify in the second column.
Be aware of this, as in some cases you might want to write a wrapper script of some sort to deal with some types of files or programs that don't properly deal with arguments.


Navigation Layout
-----------------

The "navigation_layout" parameter is a list of items to place on the navigation bar, if it's showing.  You can choose from the following:

- "back", "forward", "refresh", "stop":  the traditional browser navigation buttons.
- "zoom_in", "zoom_out":  the zoom buttons
- "bookmarks":  your bookmark buttons
- "quit":  your "I'm finished" button
- "separator": A vertical line to separate sections
- "spacer": an expanding spacer to push widgets around

The list can be specified in any valid YAML list format, but I recommend enclosing it in square braces and separating with commas.
"separator" and "spacer" can be used as many times as you wish, the others should only be used once each.

Whitelist
---------

The whitelist feature is added as a convenience to help lock down your kiosk when you don't have complete control over all the links on your kiosk pages and want to prevent users from going off to strange sites.  It's *not* a firewall or content filter, and may not behave exactly how you expect it to; so if you plan to use it, please read a bit about what it does and what it does not do.

If you don't want to use the whitelist feature, just comment it out, leave the list empty, or give it a value of "False".

What the whitelist does
~~~~~~~~~~~~~~~~~~~~~~~

You give the whitelist a list of *domains* or *hosts*, like this::

    whitelist: ["somehost.example.com", "some-local-host", "mydomain.org"]

Whenever the user clicks a link or otherwise tries to navigate to a page, the hostname is extracted from the requested URL and matched against the whitelist.  If there's a match, the page is displayed; if not, the error text.

Some things are automatic:

 - The start_url host is automatically whitelisted
 - Bookmark hosts are automatically whitelisted
 - Subdomains are also automatically whitelisted.  Thus, if you whitelist "example.com", then "foo.example.com" will be whitelisted as well (though "foo-example.com" will not, since that's actually a different domain).

If you just want to whitelist the start_url and bookmark urls and nothing else, you can just do this in the config::

    whitelist: True


What the whitelist doesn't do
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- The whitelist does not block *content* on a whitelisted page from being displayed, regardless of where the content is hosted.  As long as the page's URL is acceptable, the content is all displayed.  So, for example, if you have your images and scripts on a separate content delivery network, you don't need to whitelist that server.  You only need to whitelist hosts/domains of pages to which the user is explicitly navigating (via hyperlink, bookmark, javascript forward, etc).
- The whitelist cannot take an actual path or filename, nor does it check the port, protocol, username, or any other component of the URL other than the host or domain.  Sorry.
- If you whitelist a host, its IP will *not* be automatically whitelisted (and vice-versa); nor will a fully-qualified hostname in the whitelist automatically whitelist the hostname by itself (or vice-versa).  A url is *only* allowed when its literal hostname matches a whitelist entry.

Bugs and Limitations
====================

- SSL certificate handling is limited; I'd like the ability to add self-signed certificates, but I don't know how to accomplish this yet.  Right now you get "strict" or "ignore", which is not as flexible as one might wish.
- There is no password dialog when a page requests authentication.  You can set a single user/password set in the config file to be sent whenever a site does request it, or provide auth credentials in the URL (in a bookmark/start_url).
- Mime type handling is a little rough still, and you're bound to get 404 or network errors attempting to download documents when it's disabled.

Contributing
============

Contributions are welcome, so long as they are consistent with the spirit and intent of the browser -- that is, they are features useful in a kiosk situation, and keep the browser simple to configure.  I would also prefer that changes to features or behavior are opt-in (require a switch to enable them), unless it just makes no sense to do it that way.

License
=======

WCGBrowser is released under the terms of the GNU GPL v3.
