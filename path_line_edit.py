# -*- coding: utf-8 -*-
"""可拖放路径的 QLineEdit。

单独成模块的原因：main_window.ui 把这个类用作「提升的窗口部件」，
pyuic6 会在 ui_main_window.py 末尾生成 `from <header> import PathLineEdit`。
如果这个类还放在 ui_main.py 里，而 ui_main.py 又要导入 ui_main_window.py，
两个模块就会互相导入（循环导入）。拆出来之后依赖是单向的：

    path_line_edit.py  ←  ui_main_window.py  ←  ui_main.py  ←  main.py

改类名或模块名时，记得同步 main_window.ui 里该提升部件的 Header file。
"""

from __future__ import annotations

import os

from PyQt6.QtWidgets import QLineEdit


class PathLineEdit(QLineEdit):
    """支持拖放路径的输入框。mode: 'file' / 'dir' / 'any'。

    构造参数无法写进 .ui（uic 只按 parent 构造），所以 MainWindow 初始化时
    还会把 self.exe_edit._mode 等显式赋一遍。
    """

    def __init__(self, mode: str = "any", parent=None):
        super().__init__(parent)
        self._mode = mode
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if not path:
            return
        path = os.path.normpath(path)
        if self._mode == "dir" and not os.path.isdir(path):
            return
        if self._mode == "file" and not os.path.isfile(path):
            return
        self.setText(path)
        event.acceptProposedAction()
