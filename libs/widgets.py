"""
Copyright 2023 laynholt

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import random
import tkinter
from tkinter import ttk
from typing import Any
from config import Color, paths

import enum
from math import ceil
from random import randint

from PIL import Image, ImageTk
import pyperclip

class JustifiedCombobox(ttk.Combobox):
    """
    Creates a ttk.Combobox widget with its drop-down list items
    justified with self.justify as late as possible.
    https://stackoverflow.com/questions/48172185/how-to-justify-the-characters-in-drop-down-list-of-a-combobox
    https://stackoverflow.com/questions/64755118/how-to-change-ttk-combobox-dropdown-colors-dynamically
    """

    def __init__(self, master, **kwargs):
        ttk.Combobox.__init__(self, master, **kwargs)
        self.justify = 'center'
        self._master = master

        self._change_color()
        self._master.bind("<<ThemeChanged>>", self._change_color)

    def _justify_popdown_list_text(self):
        self._initial_bindtags = self.bindtags()
        _bindtags = list(self._initial_bindtags)
        _index_of_class_tag = _bindtags.index(self.winfo_class())
        # This dummy tag needs to be unique per object, and also needs
        # to be not equal to str(object)
        self._dummy_tag = '_' + str(self)
        _bindtags.insert(_index_of_class_tag + 1, self._dummy_tag)
        self.bindtags(tuple(_bindtags))
        _events_that_produce_popdown = tuple(['<KeyPress-Down>',
                                              '<ButtonPress-1>',
                                              '<Shift-ButtonPress-1>',
                                              '<Double-ButtonPress-1>',
                                              '<Triple-ButtonPress-1>',
                                              ])
        for _event_name in _events_that_produce_popdown:
            self.bind_class(self._dummy_tag, _event_name, self._initial_event_handle)

    def _initial_event_handle(self, event):
        _instate = str(self['state'])
        if _instate != 'disabled':
            if event.keysym == 'Down':
                self._justify()
            else:
                _ = self.tk.eval('{} identify element {} {}'.format(self, event.x, event.y))
                __ = self.tk.eval('string match *textarea {}'.format(_))
                _is_click_in_entry = bool(int(__))
                if (_instate == 'readonly') or (not _is_click_in_entry):
                    self._justify()

    def _justify(self):
        self.tk.eval('{}.popdown.f.l configure -justify {}'.format(self, self.justify))
        self.bindtags(self._initial_bindtags)

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name == 'justify':
            self._justify_popdown_list_text()

    def _change_color(self, *args):
        try:
            _style = ttk.Style()
            bg_color = _style.lookup('TFrame', 'background')
            fg_color = _style.lookup('TLabel', 'foreground')

            if bg_color != 'SystemButtonFace' and fg_color != 'SystemButtonFace':
                is_dark_mode = True if int(str(bg_color).replace("#", ''), 16) < int(str(fg_color).replace("#", ''),
                                                                                     16) else False
                new_bg_color = Color.COMBO_DROPLIST_BG_DARK if is_dark_mode else Color.COMBO_DROPLIST_BG_LIGHT
                self._master.tk.eval('[ttk::combobox::PopdownWindow {}].f.l configure -background {} -foreground {}'.format(self, new_bg_color, fg_color))
        except ValueError:
            pass


class Widget(ttk.Frame):
    def __init__(self, master):
        ttk.Frame.__init__(self, master)
        self._master = master
        self._is_done = False
        self._is_destroyed = False

    def w_destroy(self):
        if not self._is_destroyed:
            self.destroy()
            self._is_destroyed = True

    def is_done(self):
        return self._is_done

    def is_destroyed(self):
        return self._is_destroyed


class ScrollingFrame(Widget):
    def __init__(self, master):
        Widget.__init__(self, master)
        # Служебные переменные
        self._widgets = []

        # Создаем холст и фрейм в нем
        self._canvas = tkinter.Canvas(self, borderwidth=0, highlightthickness=0)
        self._frame_canvas = ttk.Frame(self._canvas)

        # Создаем вертикальный скроллбар и конектим к холсту
        self._scrollbar_vertical = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar_vertical.set)
        self._scrollbar_vertical.grid(row=0, column=1, sticky=tkinter.NS)

        # Создаем вертикальный скроллбар и конектим к холсту
        self._scrollbar_horizontal = ttk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(xscrollcommand=self._scrollbar_horizontal.set)
        self._scrollbar_horizontal.grid(row=1, column=0, sticky=tkinter.EW)

        # Конектим холст и создаем в нем окно, в роли которого выступает фрейм
        self._canvas.grid(row=0, column=0, sticky=tkinter.NSEW)
        self._window = self._canvas.create_window(0, 0, window=self._frame_canvas, anchor="nw", tags="frame")

        # Костыль для мгновенного обновления скроллбара
        self._placeholder = ttk.Label(self._frame_canvas, text="")
        self._placeholder.grid(row=0, column=0)

        # Растягиваем по всему родительскому фрейму
        # self.grid_columnconfigure(0, weight=1)
        # self.grid_rowconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # Биндим изменение размеров холста для фрейма и скроллбара
        self._frame_canvas.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Биндим прокрутку мыши в области фрейма
        self._frame_canvas.bind('<Enter>', self._bound_to_mousewheel)
        self._frame_canvas.bind('<Leave>', self._unbound_to_mousewheel)

    def _bound_to_mousewheel(self, event):
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbound_to_mousewheel(self, event):
        self._canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_frame_configure(self, event):
        # Reset the scroll region to encompass the inner frame
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        # Изменяем размер внутреннего кадра, чтобы ое соответствовал холсту
        min_width = self._frame_canvas.winfo_reqwidth()
        min_height = self._frame_canvas.winfo_reqheight()

        if self.winfo_width() >= min_width:
            new_width = self.winfo_width()
            # Прячем скроллбар, когда он не нужен
            self._scrollbar_horizontal.grid_remove()
        else:
            new_width = min_width
            # Показываем его, когда он нужен
            self._scrollbar_horizontal.grid()

        if self.winfo_height() >= min_height:
            new_height = self.winfo_height()
            # Прячем скроллбар, когда он не нужен
            self._scrollbar_vertical.grid_remove()
        else:
            new_height = min_height
            # Показываем его, когда он нужен
            self._scrollbar_vertical.grid()

        self._canvas.itemconfig(self._window, width=new_width, height=new_height)

    def _update(self):
        self._frame_canvas.update_idletasks()
        self._on_canvas_configure(None)

    def add_widget(self, widget_type='dw', **kwargs):
        self._placeholder.grid_remove()
        if widget_type == 'dw':
            self._widgets.append(DownloadWidget(self._frame_canvas, **kwargs))
        elif widget_type == 'di':
            self._widgets.append(DownloadInfo(self._frame_canvas))
        elif widget_type == 'slb':
            self._widgets.append(ScrollingListbox(self._frame_canvas))
        elif widget_type == 'sf':
            self._widgets.append(ScrollingFrame(self._frame_canvas))
        self._update()
        return self._widgets[-1]

    def get_widget(self, index):
        if index < len(self._widgets):
            return self._widgets[index]
        return None

    def w_pack(self, widget, **kwargs):
        widget.pack(**kwargs)
        self._update()

    def w_grid(self, widget, **kwargs):
        widget.grid(**kwargs)
        self._update()

    def delete_completed_widgets(self):
        doesnt_completed_widgets = []
        for widget in self._widgets:
            if widget.is_done():
                widget.w_destroy()
            else:
                doesnt_completed_widgets.append(widget)
        self._widgets = doesnt_completed_widgets

        if len(self._widgets) == 0:
            self._placeholder.grid()
        self._update()

    def delete_all_widgets(self):
        for widget in self._widgets:
            widget.w_destroy()
        self._widgets.clear()
        self._placeholder.grid()
        self._update()


class ScrollingListbox(Widget):
    """
    https://stackoverflow.com/questions/75717099/how-to-add-auto-hide-scrollbars-with-python-tkinter-in-a-listbox
    """

    def __init__(self, master, **kwargs):
        Widget.__init__(self, master)

        self._scrollbar_vertical = ttk.Scrollbar(self)
        self._scrollbar_vertical.grid(row=0, column=1, sticky=tkinter.NS)

        self._scrollbar_horizontal = ttk.Scrollbar(self, orient="horizontal")
        self._scrollbar_horizontal.grid(row=1, column=0, sticky=tkinter.EW)

        self._listbox = tkinter.Listbox(self,
                                        yscrollcommand=self._scrollbar_vertical.set,
                                        xscrollcommand=self._scrollbar_horizontal.set,
                                        **kwargs)
        self._listbox.grid(row=0, column=0, sticky=tkinter.NSEW)

        # Растягиваем по всему родительскому фрейму
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._scrollbar_vertical.config(command=self._listbox.yview)
        self._scrollbar_horizontal.config(command=self._listbox.xview)

        self._change_color()
        self.bind("<<ThemeChanged>>", self._change_color)
        self._listbox.bind("<Configure>", self._manage_scrollbar)

    def insert(self, index=tkinter.END, value=0):
        self._listbox.insert(index, value)

    def delete(self, first=0, last=tkinter.END):
        self._listbox.delete(first, last)

    def _manage_scrollbar(self, event=None):
        xview = self._listbox.xview()
        yview = self._listbox.yview()

        if yview == (0.0, 1.0):
            self._scrollbar_vertical.grid_remove()
        else:
            self._scrollbar_vertical.grid()

        if xview == (0.0, 1.0):
            self._scrollbar_horizontal.grid_remove()
        else:
            self._scrollbar_horizontal.grid()

    def _change_color(self, *args):
        _style = ttk.Style()
        bg_color = _style.lookup('TFrame', 'background')
        fg_color = _style.lookup('TLabel', 'foreground')
        if bg_color != 'SystemButtonFace' and fg_color != 'SystemButtonFace':
            self._listbox.config(bg=bg_color, fg=fg_color)

    def centering_data(self):
        self._listbox.configure(justify=tkinter.CENTER)


class ScrollingTreeView(Widget):
    """
    """

    def __init__(self, master, **kwargs):
        Widget.__init__(self, master)

        self._scrollbar_vertical = ttk.Scrollbar(self)
        self._scrollbar_vertical.grid(row=0, column=1, sticky=tkinter.NS)

        self._tree_view = ttk.Treeview(self, yscrollcommand=self._scrollbar_vertical.set, **kwargs)
        self._tree_view.grid(row=0, column=0, sticky=tkinter.NSEW)

        # Растягиваем по всему родительскому фрейму
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._scrollbar_vertical.config(command=self._tree_view.yview)

        self._tree_view.bind('<Motion>', 'break')

    def tv_column(self, *args, **kwargs):
        self._tree_view.column(*args, **kwargs)

    def tv_heading(self, *args, **kwargs):
        self._tree_view.heading(*args, **kwargs)

    def tv_insert(self, *args, **kwargs):
        self._tree_view.insert(*args, **kwargs)

    def tv_delete(self):
        self._tree_view.delete(*self._tree_view.get_children())

    def tv_simple_sorting(self, column, reverse=False):
        # получаем все значения столбцов в виде отдельного списка
        _list = [(self._tree_view.set(k, column), k) for k in self._tree_view.get_children("")]

        # сортируем список
        _list.sort(reverse=reverse)
        # переупорядочиваем значения в отсортированном порядке
        for index, (_, k) in enumerate(_list):
            self._tree_view.move(k, "", index)

    def tv_nested_sorting_children(self, column, reverse=False):
        # Получаем всех родителей
        parents = self._tree_view.get_children("")

        parents_and_children = {}
        for parent in parents:
            # получаем все значения столбцов в виде отдельного списка
            parents_and_children.update({parent: [(self._tree_view.set(child, column), child) \
                                                  for child in self._tree_view.get_children(parent)]})

            # сортируем список
            parents_and_children[parent].sort(reverse=reverse)

        # переупорядочиваем значения в отсортированном порядке
        for parent, children in parents_and_children.items():
            for index, (_, c) in enumerate(children):
                self._tree_view.move(c, parent, index + 1 + int(parent))

    def tv_get_selected(self, **kwargs):
        return self._tree_view.item(self._tree_view.focus(), **kwargs)

    def tv_get_multi_selected(self, **kwargs):
        selected = self._tree_view.selection()
        return [self._tree_view.item(index, **kwargs) for index in selected]

    def tv_open(self, tv_open=True):
        for child in self._tree_view.get_children(""):
            self._tree_view.item(child, open=tv_open)

    def tv_get_parent_of_selected(self):
        selected = self._tree_view.selection()
        parents = set(self._tree_view.parent(sel) for sel in selected)
        if '' in parents:
            parents.remove('')
        return [self._tree_view.item(parent, option='text') for parent in parents]

    def tv_get_size(self, is_hierarchical_structure=False):
        if not is_hierarchical_structure:
            return len(self._tree_view.get_children(""))

        children_size = 0
        parents = self._tree_view.get_children("")
        for parent in parents:
            children_size += len(self._tree_view.get_children(parent))
        return children_size


class DownloadWidget(Widget):
    def __init__(self, master, playlist_name: str = "", action_type: str = 'adb', progressbar_size: int = 100):
        Widget.__init__(self, master)
        self._action_types = {
            'd': "скачивания",
            'u': "обновления метаданных треков",
            'adb': "добавления треков в базу данных",
            'uf': "обновления тега любимых треков в БД"
        }
        self._action_type = self._action_types[action_type]

        self.playlist_name = tkinter.StringVar(value=f'{playlist_name}')
        self.playlist_name.trace_add('write', self._set_playlist_name)

        self.label_frame = ttk.Labelframe(self, text=self.playlist_name.get())
        self.label_frame.pack()

        self.value = tkinter.IntVar(value=0)
        self.value.trace_add('write', self._change_progressbar_state)

        self.value_max_size = tkinter.IntVar(value=progressbar_size)
        self.value_max_size.trace_add('write', self._progressbar_max_size_changed)

        self.successful_download_value = tkinter.IntVar(value=0)
        self.successful_download_value.trace_add('write', self._show_result)

        self.failed_download_value = tkinter.IntVar(value=0)
        self.failed_download_value.trace_add('write', self._show_result)

        self._label_successful = ttk.Label(self.label_frame, text='')
        self._label_failed = ttk.Label(self.label_frame, text='')

        self._label_download = ttk.Label(self.label_frame,
                                         text=f'Прогресс {self._action_type}: {0 / self.value_max_size.get()} [0 %]')
        self._label_download.pack(pady=5)

        self._progressbar = ttk.Progressbar(self.label_frame, variable=self.value, orient='horizontal',
                                            mode='determinate', length=480, maximum=self.value_max_size.get())
        self._progressbar.pack()

    def _show_result(self, *args):
        try:
            self._label_successful.config(text=f'Успешно выполнено для {self.successful_download_value.get()} композиции(-ий)')
            self._label_failed.config(text=f'Не получилось выполнить для {self.failed_download_value.get()} композиции(-ий)')
        except tkinter.TclError:
            pass

        self._progressbar.pack_forget()
        self._label_successful.pack()
        self._label_failed.pack()
        self._progressbar.pack()

    def _progressbar_max_size_changed(self, *args):
        try:
            self._label_download.config(text=f'Прогресс {self._action_type}: {0 / self.value_max_size.get()} [0 %]')
            self._progressbar.config(maximum=self.value_max_size.get())
        except tkinter.TclError:
            pass

    def _change_progressbar_state(self, *args):
        try:
            text = self._label_download['text'].split('(')[0].split(':')[0]
            downloaded_digital = f'{self.value.get()}/{self.value_max_size.get()}'
            downloaded_percentage = self.value.get() / self.value_max_size.get() * 100
            downloaded_percentage_str = "{:0.2f} %".format(downloaded_percentage)

            self._label_download.config(text=f'{text}: {downloaded_digital} [{downloaded_percentage_str}]')

            if self.value.get() >= self.value_max_size.get():
                self._is_done = True

        except tkinter.TclError:
            pass

    def _set_playlist_name(self, *args):
        try:
            self.label_frame.configure(text=self.playlist_name.get())
        except tkinter.TclError:
            pass

    def get_variables(self):
        return {
                   'progressbar_val': self.value,
                   'progressbar_size': self.value_max_size,
                   'playlist_name': self.playlist_name,
                   'successful_download': self.successful_download_value,
                   'failed_download': self.failed_download_value
        }


class DownloadInfo(Widget):
    def __init__(self, master):
        Widget.__init__(self, master)

        self.label_frame = ttk.Labelframe(self, text='Инфо')
        self.label_frame.pack()

        self.successful_download_value = tkinter.IntVar(value=0)
        self.successful_download_value.trace_add('write', self._show_result)

        self.failed_download_value = tkinter.IntVar(value=0)
        self.failed_download_value.trace_add('write', self._show_result)

        self.finish_downloading = tkinter.BooleanVar(value=False)
        self.finish_downloading.trace_add('write', self._finish_download)

        self._loading_counter = 0
        self.label_downloading = ttk.Label(self.label_frame, text='Идёт загрузка')
        self.label_downloading.pack()
        self.after(1000, self._simulate_loading)

        self._label_successful = ttk.Label(self.label_frame, text='Успешно выполнено для 0 композиции(-ий)')
        self._label_successful.pack()

        self._label_failed = ttk.Label(self.label_frame, text='Не получилось выполнить для 0 композиции(-ий)')
        self._label_failed.pack()

    def _show_result(self, *args):
        try:
            self._label_successful.config(text=f'Успешно выполнено для {self.successful_download_value.get()} композиции(-ий)')
            self._label_failed.config(text=f'Не получилось выполнить для {self.failed_download_value.get()} композиции(-ий)')
        except tkinter.TclError:
            pass

    def _finish_download(self, *args):
        try:
            self.label_downloading.config(text='Загрузка завершена.')
        except tkinter.TclError:
            pass

    def _simulate_loading(self, *args):
        try:
            if self.finish_downloading.get() is False:
                self._loading_counter = (self._loading_counter + 1) % 4
                self.label_downloading.config(text=f'Идёт загрузка{"." * self._loading_counter}')
                self.after(1000, self._simulate_loading)
        except tkinter.TclError:
            pass

    def get_variables(self):
        return {
                   'successful_download': self.successful_download_value,
                   'failed_download': self.failed_download_value,
                   'end': self.finish_downloading
        }
    

class CustomMessageType(enum.Enum):
    ANY = 'ANY'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    SUCCESS = 'SUCCESS'

class _MessageBox(tkinter.Toplevel):
    def __init__(self, master: Any, title: str, message: str, message_type: CustomMessageType = CustomMessageType.ANY):
        super().__init__(master)
        self.title(title)
        self._message = message
        self._message_type = message_type

        if message_type == CustomMessageType.INFO:
            self._image_path = paths["files"]["icon"]["info_l"]
        elif message_type == CustomMessageType.WARNING:
            self._image_path = paths["files"]["icon"]["warning_l"]
        elif message_type == CustomMessageType.ERROR:
            self._image_path = paths["files"]["icon"]["error_l"]
        elif message_type == CustomMessageType.SUCCESS:
            self._image_path = paths["files"]["icon"]["success_l"]
        else:
            self._image_path = paths["files"]["icon"]["main"]

        self._icon_path = paths["files"]["icon"]["main"]

    def create_widgets(self):
        self.configure_window()
        self.create_message_frame()
        self.create_buttons_frame()

    def configure_window(self):
        self.resizable(False, False)
        self.geometry(self.calculate_geometry())

        try:
            self.iconbitmap(self._icon_path)
        except tkinter.TclError:
            pass

        self._frame_main = ttk.Frame(self)
        self._frame_main.pack(expand=True, fill='both')

    def calculate_geometry(self, width=360, height=150):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width + random.randint(-50, 50)) // 2
        y = (screen_height - height + random.randint(-50, 50)) // 2
        return f'{width}x{height}+{x}+{y}'

    def create_message_frame(self):
        frame = ttk.Frame(self._frame_main)
        frame.pack(expand=True, fill=tkinter.BOTH)

        try:
            image = ImageTk.PhotoImage(Image.open(self._image_path))
            label_image = ttk.Label(frame, image=image) # type: ignore
            label_image.image = image  # keep a reference! # type: ignore
            label_image.pack(side=tkinter.LEFT, padx=10, pady=10)
        except Exception:
            pass

        label_text = ttk.Label(frame, text=self._message, wraplength=250)
        label_text.pack(side=tkinter.LEFT, padx=10, pady=10)

    def create_buttons_frame(self):
        frame = ttk.Frame(self._frame_main)
        frame.pack()

        button_ok = ttk.Button(frame, text="OK", command=self.destroy)
        button_ok.pack(side=tkinter.LEFT, padx=10, pady=10)

        button_copy = ttk.Button(frame, text="Копировать", command=self.copy_text)
        button_copy.pack(side=tkinter.LEFT, padx=10, pady=10)

    def copy_text(self):
        pyperclip.copy(self._message)

class CustomMessageBox:
    @staticmethod
    def show(master, title, message, message_type=CustomMessageType.ANY):
        # Создаем и показываем конкретный тип сообщения
        _MessageBox(master, title, message, message_type).create_widgets()
    
    @staticmethod
    def show_error(master, message):
        # Создаем и показываем конкретный тип сообщения
        _MessageBox(master, "Ошибка", message, CustomMessageType.ERROR).create_widgets()
    
    @staticmethod
    def show_info(master, message):
        # Создаем и показываем конкретный тип сообщения
        _MessageBox(master, "Инфо", message, CustomMessageType.INFO).create_widgets()
    
    @staticmethod
    def show_warning(master, message):
        # Создаем и показываем конкретный тип сообщения
        _MessageBox(master, "Предупреждение", message, CustomMessageType.WARNING).create_widgets()

    @staticmethod
    def show_success(master, message):
        # Создаем и показываем конкретный тип сообщения
        _MessageBox(master, "Успешно", message, CustomMessageType.SUCCESS).create_widgets()