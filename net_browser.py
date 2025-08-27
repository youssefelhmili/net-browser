import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QAction, QLineEdit, QTabWidget,
    QWidget, QVBoxLayout, QStatusBar, QFileDialog, QMessageBox, QDialog,
    QFormLayout, QPushButton, QMenu
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineDownloadItem

SETTINGS_FILE = "settings.json"
BOOKMARKS_FILE = "bookmarks.json"
HISTORY_FILE = "history.json"

# ---------------- Settings Dialog ----------------
class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.settings = settings

        layout = QFormLayout(self)

        # Homepage
        self.homepage_input = QLineEdit(self)
        self.homepage_input.setText(settings.get("homepage", "https://www.google.com"))
        layout.addRow("Homepage URL:", self.homepage_input)

        # Search Engine
        self.search_input = QLineEdit(self)
        self.search_input.setText(settings.get("search_engine", "https://www.google.com/search?q={query}"))
        layout.addRow("Search Engine Template:", self.search_input)

        # Buttons
        save_btn = QPushButton("Save", self)
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.clicked.connect(self.reject)

        layout.addRow(save_btn, cancel_btn)

    def getValues(self):
        return {
            "homepage": self.homepage_input.text(),
            "search_engine": self.search_input.text()
        }

# ---------------- Custom WebEngineView with Context Menu ----------------
class CustomWebEngineView(QWebEngineView):
    def __init__(self, browser, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.browser = browser

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        context_data = self.page().contextMenuData()

        back_action = QAction("Back", self)
        back_action.triggered.connect(self.back)
        menu.addAction(back_action)

        forward_action = QAction("Forward", self)
        forward_action.triggered.connect(self.forward)
        menu.addAction(forward_action)

        reload_action = QAction("Reload", self)
        reload_action.triggered.connect(self.reload)
        menu.addAction(reload_action)

        # Open link in new tab if a link is clicked
        if context_data.linkUrl().isValid():
            open_link_action = QAction("Open Link in New Tab", self)
            open_link_action.triggered.connect(lambda: self.browser.add_new_tab(context_data.linkUrl()))
            menu.addAction(open_link_action)

        bookmark_action = QAction("Bookmark This Page", self)
        bookmark_action.triggered.connect(lambda: self.browser._add_bookmark(self.url().toString()))
        menu.addAction(bookmark_action)

        copy_url_action = QAction("Copy Page URL", self)
        copy_url_action.triggered.connect(lambda: QApplication.clipboard().setText(self.url().toString()))
        menu.addAction(copy_url_action)

        menu.exec_(event.globalPos())

# ---------------- Browser ----------------
class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Net Browser v1")
        self.resize(1200, 800)

        self.settings = self.load_json(SETTINGS_FILE, {
            "homepage": "https://www.google.com",
            "search_engine": "https://www.google.com/search?q={query}"
        })

        self.bookmarks = self.load_json(BOOKMARKS_FILE, [])
        self.history = self.load_json(HISTORY_FILE, [])

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_urlbar)
        self.setCentralWidget(self.tabs)

        # Navigation Toolbar
        navtb = QToolBar("Navigation")
        self.addToolBar(navtb)

        back_btn = QAction(QIcon.fromTheme("go-previous"), "Back", self)
        back_btn.triggered.connect(lambda: self.tabs.currentWidget().back())
        navtb.addAction(back_btn)

        forward_btn = QAction(QIcon.fromTheme("go-next"), "Forward", self)
        forward_btn.triggered.connect(lambda: self.tabs.currentWidget().forward())
        navtb.addAction(forward_btn)

        reload_btn = QAction(QIcon.fromTheme("view-refresh"), "Reload", self)
        reload_btn.triggered.connect(lambda: self.tabs.currentWidget().reload())
        navtb.addAction(reload_btn)

        home_btn = QAction(QIcon.fromTheme("go-home"), "Home", self)
        home_btn.triggered.connect(self.navigate_home)
        navtb.addAction(home_btn)

        navtb.addSeparator()

        self.urlbar = QLineEdit()
        self.urlbar.returnPressed.connect(self.navigate_to_url)
        navtb.addWidget(self.urlbar)

        # Settings button
        settings_btn = QAction(QIcon.fromTheme("preferences-system"), "Preferences", self)
        settings_btn.triggered.connect(self.open_settings_dialog)
        navtb.addAction(settings_btn)

        # Status Bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # Menubar
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        new_tab_action = QAction("New Tab", self)
        new_tab_action.triggered.connect(lambda: self.add_new_tab())
        file_menu.addAction(new_tab_action)

        bookmark_menu = menubar.addMenu("Bookmarks")
        self.bookmark_menu = bookmark_menu
        self.update_bookmarks_menu()

        history_menu = menubar.addMenu("History")
        self.history_menu = history_menu
        self.update_history_menu()

        settings_menu = menubar.addMenu("Settings")
        preferences_action = QAction("Preferences", self)
        preferences_action.triggered.connect(self.open_settings_dialog)
        settings_menu.addAction(preferences_action)

        # First Tab
        self.add_new_tab(QUrl(self.settings["homepage"]))

    # ---------------- Tabs ----------------
    def add_new_tab(self, qurl=None, label="New Tab"):
        if qurl is None:
            qurl = QUrl(self.settings["homepage"])
        browser = CustomWebEngineView(self)
        browser.setUrl(qurl)
        browser.urlChanged.connect(lambda qurl, browser=browser: self.update_urlbar(qurl, browser))
        browser.loadFinished.connect(lambda _, browser=browser: self.update_tab_title(browser))
        browser.page().profile().downloadRequested.connect(self.on_download_requested)

        i = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(i)

    def close_tab(self, i):
        if self.tabs.count() < 2:
            return
        self.tabs.removeTab(i)

    # ---------------- Navigation ----------------
    def navigate_home(self):
        self.tabs.currentWidget().setUrl(QUrl(self.settings["homepage"]))

    def navigate_to_url(self):
        url = self.urlbar.text()
        if not url.startswith("http"):
            url = self.settings["search_engine"].replace("{query}", url)
        self.tabs.currentWidget().setUrl(QUrl(url))

    def update_urlbar(self, q=None, browser=None):
        if browser != self.tabs.currentWidget():
            return
        self.urlbar.setText(self.tabs.currentWidget().url().toString())
        self.urlbar.setCursorPosition(0)
        # Save to history
        url = self.tabs.currentWidget().url().toString()
        if url and (not self.history or self.history[-1] != url):
            self.history.append(url)
            self.save_json(HISTORY_FILE, self.history)
            self.update_history_menu()

    def update_tab_title(self, browser):
        i = self.tabs.indexOf(browser)
        if i >= 0:
            self.tabs.setTabText(i, browser.page().title())

    # ---------------- Bookmarks ----------------
    def _add_bookmark(self, url=None):
        if url is None:
            url = self.tabs.currentWidget().url().toString()
        if url not in self.bookmarks:
            self.bookmarks.append(url)
            self.save_json(BOOKMARKS_FILE, self.bookmarks)
            self.update_bookmarks_menu()
            QMessageBox.information(self, "Bookmark Added", f"Bookmarked: {url}")

    def update_bookmarks_menu(self):
        self.bookmark_menu.clear()
        for url in self.bookmarks:
            action = QAction(url, self)
            action.triggered.connect(lambda checked, url=url: self.add_new_tab(QUrl(url)))
            self.bookmark_menu.addAction(action)

    # ---------------- History ----------------
    def update_history_menu(self):
        self.history_menu.clear()
        for url in self.history[-20:]:
            action = QAction(url, self)
            action.triggered.connect(lambda checked, url=url: self.add_new_tab(QUrl(url)))
            self.history_menu.addAction(action)
        self.history_menu.addSeparator()
        clear_action = QAction("Clear History", self)
        clear_action.triggered.connect(self.clear_history)
        self.history_menu.addAction(clear_action)

    def clear_history(self):
        self.history = []
        self.save_json(HISTORY_FILE, self.history)
        self.update_history_menu()

    # ---------------- Downloads ----------------
    def on_download_requested(self, download: QWebEngineDownloadItem):
        path, _ = QFileDialog.getSaveFileName(self, "Save File", download.path())
        if path:
            download.setPath(path)
            download.accept()
            download.downloadProgress.connect(lambda rec, total: self.status.showMessage(f"Downloading {rec/total*100:.2f}%"))
            download.finished.connect(lambda: self.status.showMessage("Download finished"))

    # ---------------- Settings ----------------
    def open_settings_dialog(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_():
            new_settings = dialog.getValues()
            self.settings.update(new_settings)
            self.save_json(SETTINGS_FILE, self.settings)
            QMessageBox.information(self, "Settings Saved", "Settings updated successfully!")

    # ---------------- Helpers ----------------
    def load_json(self, filename, default):
        if os.path.exists(filename):
            try:
                with open(filename, "r") as f:
                    return json.load(f)
            except:
                return default
        return default

    def save_json(self, filename, data):
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

# ---------------- Run ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Net Browser")
    window = Browser()
    window.show()
    sys.exit(app.exec_())
