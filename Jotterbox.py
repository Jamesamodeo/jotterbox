from tkinter import filedialog, font, simpledialog, ttk
from tkinter import *
from tkcalendar import DateEntry
from pathlib import Path
from datetime import datetime, date
import os
import subprocess
import re
import abc

class App:

    class MenuAnimationManager:

        def __init__(self, frame, create_func, opened=False):
            self.frame = frame
            self.create_func = create_func
            self.opened = IntVar()
            self.opened.set(opened)
            self.animating = False

            if self.opened.get():
                self.create_func()

        def toggle(self, event=None):
            if not self.animating:
                self.set_opened(not self.opened.get())

        def set_opened(self, opened):
            self.opened.set(opened)
            self.update()

        def update(self):
            if not self.animating:
                self.animating = True
                if self.opened.get():
                    self.open()
                else:
                    self.close()

        def open(self):
            self.create_func()
            self.open_step()

        def open_step(self):
            self.frame.config(height=self.frame.cget('height') + App.MENU_ANIMATION_STEP)
            if self.frame.cget('height') < App.MENU_HEIGHT:
                self.frame.after(App.MENU_ANIMATION_SPEED, self.open_step)
            else:
                self.frame.config(height=App.MENU_HEIGHT)
                self.animating = False

        def close(self):
            self.close_step()

        def close_step(self):
            self.frame.config(height=self.frame.cget('height') - App.MENU_ANIMATION_STEP)
            if self.frame.cget('height') > 0:
                self.frame.after(App.MENU_ANIMATION_SPEED, self.close_step)
            else:
                self.frame.grid_forget()
                self.animating = False

    class TagMenuItem:

        COLOUR = 'white'
        HOVER_COLOUR = 'yellow'
        ACTIVE_COLOUR = 'orange'

        def __init__(self, tag):
            self.tag = tag
            self.label = None
            self.active = False
            self.hovered = False

        def on_click(self, event=None):
            self.active = not self.active
            self.update_colour()

        def on_hover(self, event=None):
            self.hovered = True
            self.update_colour()

        def on_unhover(self, event=None):
            self.hovered = False
            self.update_colour()

        def update_colour(self):
            colour = App.TagMenuItem.COLOUR
            if self.active:
                colour = App.TagMenuItem.ACTIVE_COLOUR
            elif self.hovered:
                colour = App.TagMenuItem.HOVER_COLOUR
            self.label.configure(fg=colour)

    class Note:

        FIELD_SEPARATOR = '\t'
        TAG_SEPARATOR = ' '

        def __init__(self, timestamp=None):
            self.timestamp = timestamp
            if not timestamp:
                self.timestamp = datetime.now()

            self.file = None
            self.file_line = None
            self.text = None
            self.tags = []

            self.deleted = False

        def serialise(self):
            fields = [
                self.timestamp.isoformat(),
                self.text,
                App.Note.TAG_SEPARATOR.join(self.tags)
            ]
            return App.Note.FIELD_SEPARATOR.join(fields)

        @staticmethod
        def deserialise(file_line, file, data):
            parts = data.split(App.Note.FIELD_SEPARATOR)
            fields = {}
            fields['file'] = file
            fields['file_line'] = file_line
            fields['timestamp'] = datetime.fromisoformat(parts[0])
            fields['text'] = parts[1]
            fields['tags'] = list(filter(None, parts[2].split(App.Note.TAG_SEPARATOR)))
            return fields

    class Notebook:
        
        def __init__(self, dir, title=None):
            self.dir = dir
            self.title = title
            self.notes = {}
            self.notes_deleted = []
            self.tag_dict = {}
            self.loaded_files = []
            self.fully_loaded = False

        def close(self):
            return

        def load(self):
            # Setup which files will be initially loaded
            initial_files = [
                self.dir /  (self.title + '_' + datetime.now().strftime('%Y-%m-%d') + '.tsv')
            ]

            # Load notes from initially loaded files
            for file in initial_files:
                if file.exists():
                    self.load_notes_from_file(file)

        def save(self):
            file_dict = {}
            for timestamp, note in self.notes.items():
                if note.file is None:
                    note.file = self.dir /  (self.title + '_' + note.timestamp.strftime('%Y-%m-%d') + '.tsv')
                if note.file in file_dict:
                    file_dict[note.file].append(note)
                else:
                    file_dict[note.file] = [note]
            
            # Save all deleted notes that exist in a file
            for note in self.notes_deleted:
                if not note.file is None:
                    if note.file in file_dict:
                        file_dict[note.file].append(note)
                    else:
                        file_dict[note.file] = [note]
            self.notes_deleted.clear()

            # For each updated file, save notes into that file
            for file in file_dict.keys():
                self.save_notes_to_file(file, file_dict[file])

        # Load notebook settings from NOTEBOOK_SETTINGS_FILENAME within notebook directory.
        def load_settings(self):
            data = App.load_file(Path(self.dir / App.NOTEBOOK_SETTINGS_FILENAME))
            settings = []

            if data:
                try:
                    settings = data.split(',')[:-1]
                    self.title = settings[0]
                except:
                    return False
            else:
                return False

        # Save notebook settings into NOTEBOOK_SETTINGS_FILENAME within notebook directory.
        def save_settings(self):
            data = ''
            settings = []
            settings.append(self.title)
            for setting in settings:
                data += setting + ','

            App.save_file(Path(self.dir / App.NOTEBOOK_SETTINGS_FILENAME), data, hidden=True)

        # Load notes from a file.
        def load_notes_from_file(self, file):
            if file not in self.loaded_files:
                lines = []
                with open(file, 'r') as f:
                    lines = f.read().splitlines()
                
                file_line = 0
                for line in lines:

                    # Deserialise and load note
                    self.create_note(fields=App.Note.deserialise(file_line, file, line))
                    
                    file_line += 1
                
                self.loaded_files.append(file)

        # Save notes into a file (including deletions).
        def save_notes_to_file(self, file, notes):
            # If file doesn't exist yet, write all notes sequentially
            if not file.exists():
                id = 0
                with open(file, 'w') as f:
                    for note in notes:
                        note.file_line = id
                        id += 1
                        f.write(note.serialise() + '\n')
            else:
                # Gather lines from file
                lines = []
                with open(file, 'r') as f:
                    lines = f.readlines()

                for note in notes:
                    if note.deleted:  # Mark deleted notes for removal
                        lines[note.file_line] = None
                    else:
                        if note.file_line is None:  # Append new notes to file lines
                            note.file_line = len(lines)
                            lines.append(note.serialise() + '\n')
                        
                        else:  # Update file line for existing notes
                            lines[note.file_line] = note.serialise() + '\n'
                
                # Remove deleted notes from file lines
                i = 0
                while i < len(lines):
                    if lines[i] is None:
                        lines.pop(i)
                    else:
                        i += 1

                # Save updated lines into file
                with open(note.file, 'w') as f:
                    f.writelines(lines)

        def load_all_files(self):
            files = list(self.dir.glob('*.tsv'))
            for file in files:
                self.load_notes_from_file(file)

        def create_note(self, fields=None):
            note = None
            if fields:
                note = App.Note(fields['timestamp'])
                note.file = fields['file']
                note.file_line = fields['file_line']
                self.set_note_text(note, fields['text'])
                self.set_note_tags(note, fields['tags'])
            else:
                note = App.Note()

            self.notes[note.timestamp] = note              

            return note

        def delete_note(self, note):
            self.notes_deleted.append(self.notes.pop(note.timestamp))
            for tag in note.tags:
                self.remove_tag_from_note(note, tag)
            note.deleted = True

        # Load tags of loaded notes and setup a dictionary mapping tags to notes that include them
        def update_tag_dict(self):
            self.tag_dict.clear()
            for timestamp, note in self.notes.items():
                for tag in note.tags:
                    if tag not in self.tag_dict.keys():
                        self.tag_dict[tag] = { note.timestamp : note }
                    else:
                        self.tag_dict[tag][note.timestamp] = note
        
        def add_tag_to_note(self, note, tag):
            note.tags.append(tag)
            if tag not in self.tag_dict.keys():
                self.tag_dict[tag] = { note.timestamp : note }
            else:
                self.tag_dict[tag][note.timestamp] = note
        
        def remove_tag_from_note(self, note, tag):
            note.tags.remove(tag)
            self.tag_dict[tag].pop(note.timestamp)
            if len(self.tag_dict[tag]) == 0:
                self.tag_dict.pop(tag)


        def set_note_tags(self, note, new_tags):
            old_tags = note.tags.copy()
            for tag in old_tags:
                if tag not in new_tags:
                    self.remove_tag_from_note(note, tag)
            for tag in new_tags:
                if tag not in old_tags:
                    self.add_tag_to_note(note, tag)

        def set_note_text(self, note, text):
            note.text = text

        def query(self, range_start=None, range_end=None, filter_tags=None):
            result = []
            timestamps = sorted(self.notes.keys())
            start = 0

            # Binary search for range_start in the notes' timestamps
            if range_start is not None and len(timestamps) > 0:
                l = 0
                r = len(timestamps) - 1
                mid = 0
                while l <= r:
                    mid = (l + r) // 2
                    if timestamps[mid].date() < range_start:
                        l = mid + 1
                    elif timestamps[mid].date() > range_start:
                        r = mid - 1
                    else:
                        break

                if timestamps[mid].date() >= range_start:
                    while mid > 0 and timestamps[mid-1].date() == timestamps[mid].date():
                        mid -= 1
                    start = mid
                else:
                    start = len(timestamps)

            for i in range(start, len(timestamps)):
                if range_end is not None and timestamps[i].date() > range_end:
                    break
                include = False
                if filter_tags is None:
                    include = True
                else:
                    for tag in self.notes[timestamps[i]].tags:
                        if tag in filter_tags:
                            include = True
                            break
                if include:
                    result.append(self.notes[timestamps[i]])

            return result

    class CanvasDrawing(metaclass=abc.ABCMeta):
        
        max_width = None

        def __init__(self, canvas, index, items=[], x=0, y=0):
            self.canvas = canvas
            self.index = index
            self.items = items
            self.x = x
            self.y = y

            self.item_shapes = []      
            for item in self.items:
                self.item_shapes.append(self.canvas.coords(item))

        def bind(self, sequence, func):
            for item in self.items:
                self.canvas.tag_bind(item, sequence, func)

        def set_state(self, state):
            for item in self.items:
                self.canvas.itemconfig(item, state=state)
        
        def reposition(self, x=None, y=None):
            # Update position fields
            self.x = x if x else self.x
            self.y = y if y else self.y
            self.update_coords()            

        # Update coords of all points in all items to reflect new position
        def update_coords(self):
            for i in range(len(self.items)):
                coords = self.item_shapes[i]
                new_coords = []
                for j in range(0, len(coords), 2):
                    new_coords.append(coords[j]   + self.x)
                    new_coords.append(coords[j+1] + self.y)
                self.canvas.coords(self.items[i], new_coords)

        def remove(self):
            for item in self.items:
                self.canvas.delete(item)

        def get_bottom_y(self):
            try:
                coords = self.canvas.bbox(self.items[0])
                return coords[3]
            except:
                return None

        @abc.abstractmethod
        def update_width(self):
            pass

    class NoteDrawing(CanvasDrawing):

        font = None
        
        def __init__(self, canvas, index, note):
            self.note = note

            initial_text = self.note.text if self.note.text else ''
            drawing = canvas.create_text(0, 0, text=initial_text, fill=App.TEXT_COLOUR, activefill=App.TEXT_COLOUR_HOVER, anchor=NW, width=App.CanvasDrawing.max_width, font=App.NoteDrawing.font)
            
            super().__init__(canvas, index, items=[drawing])

        def update_text(self, show_tags=False):
            if show_tags:
                self.canvas.itemconfigure(self.items[0], text=App.Note.TAG_SEPARATOR.join(self.note.tags))
            else:
                self.canvas.itemconfigure(self.items[0], text=self.note.text)

        def update_width(self):
            self.canvas.itemconfigure(self.items[0], width=App.CanvasDrawing.max_width)

    class DateMarkerDrawing(CanvasDrawing):

        def __init__(self, canvas, index):
            super().__init__(canvas, index)

    class NewButtonDrawing(CanvasDrawing):

        RECT_COLOUR = '#2C2F30'
        PLUS_COLOUR = 'grey'
        WIDTH = 150
        HEIGHT = 24
        PLUS_SIZE = 13
        PLUS_THICKNESS = 2
        PLUS_X_CENTER = 12
        PLUS_Y_CENTER = HEIGHT // 2

        def __init__(self, canvas, index):
            rect = canvas.create_rectangle(
                0, 0, 
                App.NewButtonDrawing.WIDTH, App.NewButtonDrawing.HEIGHT, 
                fill=App.NewButtonDrawing.RECT_COLOUR, outline=App.NewButtonDrawing.RECT_COLOUR, state=HIDDEN)
            plus_a = canvas.create_rectangle(
                App.NewButtonDrawing.PLUS_X_CENTER-(App.NewButtonDrawing.PLUS_SIZE//2), App.NewButtonDrawing.PLUS_Y_CENTER-(App.NewButtonDrawing.PLUS_THICKNESS//2), 
                App.NewButtonDrawing.PLUS_X_CENTER+(App.NewButtonDrawing.PLUS_SIZE//2), App.NewButtonDrawing.PLUS_Y_CENTER+(App.NewButtonDrawing.PLUS_THICKNESS//2), 
                fill=App.NewButtonDrawing.PLUS_COLOUR, outline=App.NewButtonDrawing.PLUS_COLOUR, state=HIDDEN)
            plus_b = canvas.create_rectangle(
                App.NewButtonDrawing.PLUS_X_CENTER-(App.NewButtonDrawing.PLUS_THICKNESS//2), App.NewButtonDrawing.PLUS_Y_CENTER-(App.NewButtonDrawing.PLUS_SIZE//2), 
                App.NewButtonDrawing.PLUS_X_CENTER+(App.NewButtonDrawing.PLUS_THICKNESS//2), App.NewButtonDrawing.PLUS_Y_CENTER+(App.NewButtonDrawing.PLUS_SIZE//2), 
                fill=App.NewButtonDrawing.PLUS_COLOUR, outline=App.NewButtonDrawing.PLUS_COLOUR, state=HIDDEN)
            
            super().__init__(canvas, index, items=[rect, plus_a, plus_b])

        def update_width(self):
            self.item_shapes[0][2] = self.item_shapes[0][0] + min(App.NewButtonDrawing.WIDTH, App.CanvasDrawing.max_width)
            self.update_coords()

    MENU_HEIGHT = 40
    MENU_ANIMATION_SPEED = 5
    MENU_ANIMATION_STEP = 5
    TEXT_COLOUR = 'white'
    TEXT_COLOUR_HOVER = 'orange'
    ENTRY_BG_COLOUR = '#2C2F30'
    CANVAS_BG_COLOUR = '#232725'
    MENU_BG_COLOUR = '#2C2F30'
    DRAWING_Y_GAP = 8
    CANVAS_Y_MARGIN_TOP = 35
    CANVAS_Y_MARGIN_BOTTOM = 35
    CANVAS_X_MARGIN = 50
    ENTRY_TEXT_WIDTH = 55
    ENTRY_TEXT_HEIGHT = 1
    TAG_TEXT_HEIGHT = 1
    ENTRY_TAG_TEXT_GAP = 8
    DATE_MENU_ENTRY_START_X = 100
    DATE_MENU_ENTRY_END_X = 220
    WINDOW_MIN_WIDTH_OFFSET = 80
    WINDOW_MIN_HEIGHT_OFFSET = 200
    WINDOW_DEFAULT_WIDTH = 800
    WINDOW_DEFAULT_HEIGHT = 500
    WINDOW_TITLE_ROOT = 'Jotterbox'
    NOTEBOOK_SETTINGS_FILENAME = '.jotterbox'
    APP_SETTINGS_PATH = os.path.dirname(os.path.realpath(__file__)) + '/settings.txt'
    ICON_PATH = os.path.dirname(os.path.realpath(__file__)) + '/Jotterbox.ico'

    # Initialise window.
    def __init__(self):
        self.root = Tk()
        self.root.withdraw()
        self.root.title(App.WINDOW_TITLE_ROOT)
        self.root.iconbitmap(App.ICON_PATH)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.option_add('*tearOff', FALSE)
        self.root.geometry('{}x{}'.format(App.WINDOW_DEFAULT_WIDTH, App.WINDOW_DEFAULT_HEIGHT))
        self.root.minsize(2 * App.CANVAS_X_MARGIN + App.WINDOW_MIN_WIDTH_OFFSET, App.MENU_HEIGHT + App.WINDOW_MIN_HEIGHT_OFFSET)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.frame = Frame(self.root)
        self.frame.grid(column=0, row=0, sticky=(N, W, E, S))
        self.frame.grid_propagate(False)

        self.notebook = None
        self.loading_dir = None
        self.editing_note_drawing = None
        self.tab_held = False
        self.filtered_notes = []
        self.note_drawings = []
        self.canvas_drawings = []
        self.tag_menu_items = []
        self.new_button_drawing = None
        self.date_menu_range_start = None
        self.date_menu_range_end = None

        self.date_menu_mode = StringVar()
        self.date_menu_mode.set('Today')

        App.NoteDrawing.font = font.Font(family='Roboto Mono', size=11)
        App.CanvasDrawing.max_width = 100  

        self.create_widgets()
        self.create_bindings()    
        self.create_menu_bar()

        if self.load_app_settings():
            if self.loading_dir is not None:
                self.notebook = App.Notebook(self.loading_dir)
                self.notebook.load_settings()
                self.load_notebook()

        self.update_date_menu()
        self.notes_canvas.focus_set()
        self.root.deiconify()
        self.root.mainloop()

    # Create window's widgets and place them.
    def create_widgets(self):
        self.frame.rowconfigure(0, weight=0)
        self.frame.rowconfigure(1, weight=0)
        self.frame.rowconfigure(2, weight=1)
        self.frame.columnconfigure(0, weight=1)

        self.date_menu_frame = Frame(self.frame, bg=App.MENU_BG_COLOUR, width=App.MENU_HEIGHT)
        self.date_menu_frame_animator = App.MenuAnimationManager(self.date_menu_frame, lambda: self.date_menu_frame.grid(column=0, row=0, sticky=(N, W, E)))

        self.date_menu_selector = ttk.Combobox(self.date_menu_frame, textvariable=self.date_menu_mode, state='readonly', width=7, values=('Today', 'All', 'Range...'), takefocus=0)
        self.date_menu_selector.place(x=10, y=10)

        self.date_menu_entry_start = DateEntry(self.date_menu_frame, values="Text", state='readonly', date_pattern="yyyy-mm-dd", takefocus=0)
        self.date_menu_entry_start.place(x=App.DATE_MENU_ENTRY_START_X, y=10)
        self.date_menu_range_start = self.date_menu_entry_start.get_date()

        self.date_menu_entry_end = DateEntry(self.date_menu_frame, values="Text", state='readonly', date_pattern="yyyy-mm-dd", takefocus=0)
        self.date_menu_entry_end.place(x=App.DATE_MENU_ENTRY_END_X, y=10)
        self.date_menu_range_end = self.date_menu_entry_end.get_date()

        self.tag_menu_frame = Frame(self.frame, bg=App.MENU_BG_COLOUR, width=App.MENU_HEIGHT)
        self.tag_menu_frame_animator = App.MenuAnimationManager(self.tag_menu_frame, lambda: self.tag_menu_frame.grid(column=0, row=1, sticky=(N, W, E)))

        self.notes_frame = Frame(self.frame, bg=App.CANVAS_BG_COLOUR)
        self.notes_frame.grid(column=0, row=2, sticky=(N, W, E, S))

        self.notes_canvas = Canvas(self.notes_frame, bg=App.CANVAS_BG_COLOUR, scrollregion=(0,0,0,1000), highlightthickness=0)
        self.notes_scrollbar = Scrollbar(self.notes_frame, orient=VERTICAL, command=self.notes_canvas.yview)
        self.notes_scrollbar.pack(side=RIGHT, fill=Y)
        self.notes_canvas.config(yscrollcommand=self.notes_scrollbar.set)
        self.notes_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.text_entry = Text(self.notes_canvas, width=App.ENTRY_TEXT_WIDTH, height=App.ENTRY_TEXT_HEIGHT, bg=App.ENTRY_BG_COLOUR, fg='white', font=App.NoteDrawing.font, insertbackground='white', borderwidth=0)
        self.tag_entry = Text(self.notes_canvas, width=App.ENTRY_TEXT_WIDTH, height=App.TAG_TEXT_HEIGHT, bg=App.ENTRY_BG_COLOUR, fg='orange', font=App.NoteDrawing.font, insertbackground='white', borderwidth=0)

        self.new_button_drawing = App.NewButtonDrawing(self.notes_canvas, len(self.canvas_drawings))
        self.new_button_drawing.reposition(x=App.CANVAS_X_MARGIN)
        self.canvas_drawings.append(self.new_button_drawing)

    # Create window's menu bar and setup with commands.
    def create_menu_bar(self):
        menubar = Menu(self.root)
        menu_file = Menu(menubar)
        menu_view = Menu(menubar)
        menubar.add_cascade(label='File', menu=menu_file)
        menubar.add_cascade(label='View', menu=menu_view)

        menu_file.add_command(label='New Notebook', command=self.new_notebook, accelerator='Ctrl+N')
        menu_file.add_command(label='Open Notebook', command=self.open_notebook, accelerator='Ctrl+O')
        menu_file.add_command(label='Save Notebook', command=self.save_notebook, accelerator='Ctrl+S')
        menu_file.add_command(label='Close Notebook', command=self.close_notebook)
        menu_file.add_command(label='Show Notebook in Explorer', command=self.show_notebook_in_explorer)
        menu_file.add_separator()
        export = Menu(menubar)
        menu_file.add_cascade(label='Export...', menu=export)
        export.add_command(label='Jotterbox File (.tsv)', command=lambda e: self.export('TSV'))
        menu_file.add_separator()
        menu_file.add_command(label='Exit', command=self.on_close)

        menu_view.add_checkbutton(label='Show Date Menu', command=self.date_menu_frame_animator.update, onvalue=1, offvalue=0, variable=self.date_menu_frame_animator.opened, accelerator='Ctrl+D')
        menu_view.add_checkbutton(label='Show Tag Menu', command=self.tag_menu_frame_animator.update, onvalue=1, offvalue=0, variable=self.tag_menu_frame_animator.opened, accelerator='Ctrl+T')

        self.root['menu'] = menubar

    # Create widget bindings.
    def create_bindings(self):

        self.root.bind('<Control-n>', self.new_notebook)
        self.root.bind('<Control-o>', self.open_notebook)
        self.root.bind('<Control-s>', self.save_notebook)
        self.root.bind('<Control-d>', self.date_menu_frame_animator.toggle)
        self.root.bind('<Control-t>', self.tag_menu_frame_animator.toggle)

        self.date_menu_selector.bind('<<ComboboxSelected>>', self.on_date_menu_mode_change)
        self.date_menu_entry_start.bind('<<DateEntrySelected>>', self.on_date_menu_range_change)
        self.date_menu_entry_end.bind('<<DateEntrySelected>>', self.on_date_menu_range_change)

        self.notes_canvas.bind('<Configure>', self.on_canvas_resize)
        self.notes_canvas.bind('<Key>', self.on_key_press)
        self.notes_canvas.bind('<Tab>', self.on_tab_press)
        self.notes_canvas.bind('<KeyRelease-Tab>', self.on_tab_release)
        self.notes_canvas.bind('<Button-1>', self.on_canvas_click)
        self.notes_canvas.bind('<MouseWheel>', self.on_mouse_wheel)

        self.text_entry.bind('<Return>', self.note_edit_submit)
        self.text_entry.bind('<Escape>', self.note_edit_cancel)
        self.text_entry.bind('<Tab>', self.note_edit_switch)
        self.tag_entry.bind('<Return>', self.note_edit_submit)
        self.tag_entry.bind('<Escape>', self.note_edit_cancel)
        self.tag_entry.bind('<Tab>', self.note_edit_switch)

        self.new_button_drawing.bind('<Button-1>', self.new_note)

    # Load application settings from NOTEBOOK_SETTINGS_FILENAME.
    def load_app_settings(self):
        data = App.load_file(Path(App.APP_SETTINGS_PATH))

        if data:
            try:
                settings = data.split(',')[:-1]
                if settings[0] != '':
                    self.loading_dir = Path(settings[0])
                self.date_menu_frame_animator.set_opened(int(settings[1]))
                self.tag_menu_frame_animator.set_opened(int(settings[2]))
                self.root.geometry(settings[3])
                self.root.state(settings[4])
                self.date_menu_mode.set(settings[5])
                self.date_menu_entry_start.set_date(date.fromisoformat(settings[6]))
                self.date_menu_entry_end.set_date(date.fromisoformat(settings[7]))
                self.date_menu_range_start = self.date_menu_entry_start.get_date()
                self.date_menu_range_end = self.date_menu_entry_end.get_date()
                return True
            except:
                return False
        else:
            return False

    # Save application settings into NOTEBOOK_SETTINGS_FILENAME.
    def save_app_settings(self):
        data = ''
        settings = []
        settings.append(self.notebook.dir if self.notebook else '')
        settings.append(str(self.date_menu_frame_animator.opened.get()))
        settings.append(str(self.tag_menu_frame_animator.opened.get()))
        settings.append(str(self.root.geometry()))
        settings.append(self.root.state())
        settings.append(self.date_menu_mode.get())
        settings.append(self.date_menu_range_start.isoformat())
        settings.append(self.date_menu_range_end.isoformat())
        for setting in settings:
            data += str(setting) + ','

        self.save_file(Path(App.APP_SETTINGS_PATH), data)
    
    # Save all loaded notes. Includes removing deleted notes from where they were loaded.
    def save_notebook(self, event=None):
        if self.notebook:
            self.notebook.save()

    # Load database of notes from the current notebook.
    def load_notebook(self, event=None):
        self.notebook.load()
        self.update_canvas_drawings()

        #self.update_tag_menu()
        self.new_button_drawing.set_state(NORMAL)
        self.root.title('{} - {}'.format(App.WINDOW_TITLE_ROOT, str(self.notebook.dir)))

    # Create a new notebook (database of notes) after prompting for its path. Also, initialise the notebook's title with a prompt.
    def new_notebook(self, event=None):
        input = filedialog.askdirectory(initialdir='/', title='Select Directory')
        if input != '':
            dir = Path(input)
            title = simpledialog.askstring('', 'Name your notebook', parent=self.root)
            self.notebook = App.Notebook(dir, title)
            self.load_notebook()

    # Load a notebook (its settings and database of notes) after prompting for its path.
    def open_notebook(self, event=None):
        input = filedialog.askdirectory(initialdir='/', title='Select Directory')
        if input != '':
            if self.notebook:
                self.close_notebook()
            dir = Path(input)
            self.notebook = App.Notebook(dir)
            self.notebook.load_settings()
            self.load_notebook()
    
    # Close the currently opened notebook.
    def close_notebook(self):
        if self.notebook:
            self.notebook.close()
            self.notebook = None

            while len(self.note_drawings) > 0:
                    self.delete_note_drawing(self.note_drawings[0])

            self.new_button_drawing.set_state(HIDDEN)

            if self.editing_note_drawing:
                self.note_edit_cancel()

            self.update_tag_menu()
            self.update_canvas_drawing_pos(self.new_button_drawing.index)

        self.root.title(App.WINDOW_TITLE_ROOT)

    # Open Windows explorer at the path of the current notebook's directory (if a notebook is open).
    def show_notebook_in_explorer(self):
        if self.notebook is not None:
            subprocess.Popen(r'explorer "'+os.path.normpath(self.notebook.dir)+'"')

    # Export the currently displayed notes to a file.
    def export(self, format):
        if self.notebook:

            # Create export folder if it doesn't exist already
            if not os.path.exists(self.notebook.dir / 'Export'):
                os.mkdir(self.notebook.dir / 'Export')
            
            # Set up file dialog's file type options according to export format
            filetypes = [('All files', '*.*')]
            if format == 'TSV':
                filetypes.insert(0, ('Tab-separated values', '*.tsv'))

            # Prompt user for a file path into which to create the exported file
            path = filedialog.asksaveasfilename(
                initialdir=self.notebook.dir / 'Export',
                initialfile='export_{}.tsv'.format(self.notebook.title),
                filetypes=filetypes,
                title='Export Notes')

            # Write the data of all displayed notes into the file according to export format
            f = open(path, 'w')
            if format == 'TSV':
                for note_drawing in self.note_drawings:
                    f.write(note_drawing.note.serialise() + '\n')
            f.close()

    # Create a new, empty note and drawing for which the editor is opened.
    def new_note(self, event=None):
        new_note = self.notebook.create_note()
        new_note_drawing = self.create_note_drawing(new_note)
        self.note_edit_start(self.canvas_drawings[new_note_drawing.index], height=App.ENTRY_TEXT_HEIGHT)

    def create_tag_menu_item(self, tag):
        tag_menu_item = App.TagMenuItem(tag)
        tag_menu_item.label = Label(self.tag_menu_frame, text=tag, fg=App.TagMenuItem.COLOUR, bg=App.MENU_BG_COLOUR, font=App.NoteDrawing.font)
        tag_menu_item.label.place(x=10+100*len(self.tag_menu_items), y=10)

        tag_menu_item.label.bind('<Button-1>', lambda e: self.on_tag_menu_item_click(tag_menu_item))
        tag_menu_item.label.bind('<Enter>', tag_menu_item.on_hover)
        tag_menu_item.label.bind('<Leave>', tag_menu_item.on_unhover)

        self.tag_menu_items.append(tag_menu_item)

    def delete_tag_menu_item(self, item):
        item.label.destroy()
        self.tag_menu_items.remove(item)

    def create_note_drawing(self, note):
        # Create new note drawing as the last canvas drawing (before the entry button)
        index = len(self.canvas_drawings)
        if self.new_button_drawing:
            index -= 1
        note_drawing = App.NoteDrawing(self.notes_canvas, index, note)
        note_drawing.reposition(x=App.CANVAS_X_MARGIN)
        self.canvas_drawings.insert(index, note_drawing)
        self.note_drawings.append(note_drawing)
        note_drawing.bind('<Button-1>', lambda e: self.on_note_drawing_click(note_drawing))

        # Update positions of new note drawing and entry button
        self.update_canvas_drawing_pos(index)
        if self.new_button_drawing:
            self.new_button_drawing.index = len(self.canvas_drawings) - 1
            self.update_canvas_drawing_pos(self.new_button_drawing.index)

        return note_drawing            

    def delete_note_drawing(self, note_drawing):
        note_drawing.remove()

        self.canvas_drawings.pop(note_drawing.index)
        self.note_drawings.remove(note_drawing)

        # Update positions of all canvas drawings below deleted note drawing
        for i in range(note_drawing.index, len(self.canvas_drawings)):
            self.canvas_drawings[i].index = i
            self.update_canvas_drawing_pos(i)

    def update_canvas_drawing_pos(self, index):
        y = App.CANVAS_Y_MARGIN_TOP
        if index > 0:
            y = App.DRAWING_Y_GAP + self.canvas_drawings[index - 1].get_bottom_y()

        self.canvas_drawings[index].reposition(y=y)

    def update_canvas_drawings(self):
        # Delete all note drawings
        while len(self.note_drawings):
            self.delete_note_drawing(self.note_drawings[0])
        self.note_drawings.clear()

        # Determine date range and mode to filter with based on date menu selections
        range_start = datetime.today().date()
        range_end = datetime.today().date()
        mode = self.date_menu_mode.get()
        if mode != 'Today':
            if mode == 'Range...':
                range_start = self.date_menu_range_start
                range_end = self.date_menu_range_end
            elif mode == 'All':
                range_start = None
                range_end = None

            # If notes may be loaded from other days, all note files in the notebook directory should be loaded
            if not self.notebook.fully_loaded:
                self.notebook.load_all_files()
                self.notebook.fully_loaded = True
                self.update_tag_menu()

        # Determine tags to filter with based on currently active tag menu items
        filter_tags = []
        for tag_menu_item in self.tag_menu_items:
            if tag_menu_item.active:
                filter_tags.append(tag_menu_item.tag)
        if len(filter_tags) == 0:
            filter_tags = None

        # Filter all loaded notes according to date and tag filters, then add all resulting notes to the canvas
        filtered_notes = self.notebook.query(range_start=range_start, range_end=range_end, filter_tags=filter_tags)
        for note in filtered_notes:
            self.create_note_drawing(note)

        # Update entry button position
        if self.new_button_drawing:
            self.update_canvas_drawing_pos(self.new_button_drawing.index)

        self.update_scrollbar()

    def update_scrollbar(self):
        canvas_drawings_bottom = self.canvas_drawings[-1].get_bottom_y()
        if self.editing_note_drawing:
            canvas_drawings_bottom = self.notes_canvas.bbox(self.tag_entry_window)[3]

        if canvas_drawings_bottom:
            canvas_drawings_bottom += App.CANVAS_Y_MARGIN_BOTTOM
            self.notes_canvas.config(scrollregion=(0,0,0,canvas_drawings_bottom))

            # Hide scrollbar if entire scroll region is visible
            if self.notes_scrollbar.get() == (0.0, 1.0):
                self.notes_scrollbar.pack_forget()
            else:
                self.notes_scrollbar.pack(side=RIGHT, fill=Y)

    def update_tag_menu(self):
        while len(self.tag_menu_items):
            self.delete_tag_menu_item(self.tag_menu_items[0])
        self.tag_menu_items.clear()

        if self.notebook:
            for tag in self.notebook.tag_dict.keys():
                self.create_tag_menu_item(tag)

    def update_date_menu(self):
        mode = self.date_menu_mode.get()
        if mode == 'Range...':
            self.date_menu_entry_start.place(x=App.DATE_MENU_ENTRY_START_X, y=10)
            self.date_menu_entry_end.place(x=App.DATE_MENU_ENTRY_END_X, y=10)
        else:
            self.date_menu_entry_start.place_forget()
            self.date_menu_entry_end.place_forget()        

    # Open the note editor for a given note drawing.
    def note_edit_start(self, note_drawing, height=None, event=None):
        if self.editing_note_drawing:
            self.note_edit_cancel()
        self.editing_note_drawing = note_drawing
        coords = self.notes_canvas.bbox(note_drawing.items[0])
        x = coords[0]
        y = coords[1]
        if not height:
            height = (coords[3] - coords[1]) / 20

        self.text_entry.config(height=height)
        self.text_entry_window = self.notes_canvas.create_window(x, y, anchor=NW, window=self.text_entry)
        self.tag_entry_window = self.notes_canvas.create_window(x, coords[3] + App.ENTRY_TAG_TEXT_GAP, anchor=NW, window=self.tag_entry)
        self.new_button_drawing.set_state(HIDDEN)

        self.text_entry.focus_set()
        self.text_entry.config(state='normal')
        self.text_entry.delete('1.0', 'end')
        self.text_entry.insert('1.0', self.editing_note_drawing.note.text if self.editing_note_drawing.note.text else '')
        
        self.tag_entry.config(state='normal')
        self.tag_entry.delete('1.0', 'end')
        self.tag_entry.insert('1.0', App.Note.TAG_SEPARATOR.join(self.editing_note_drawing.note.tags))

        self.on_tab_release()

    # Switch focus between textboxes of the note editor.
    def note_edit_switch(self, event=None):
        if self.text_entry == self.text_entry.focus_displayof():
            self.tag_entry.focus()
        else:
            self.text_entry.focus()
        return 'break'

    # Submit the contents of the note editor's textboxes.
    def note_edit_submit(self, event=None):
        text = self.text_entry.get('1.0', 'end-1c')
        tags = list(filter(None, self.tag_entry.get('1.0', 'end-1c').split(App.Note.TAG_SEPARATOR)))
        
        if len(text.strip()) == 0:
            self.delete_note_drawing(self.editing_note_drawing)
            self.notebook.delete_note(self.editing_note_drawing.note)
        else:
            self.notebook.set_note_text(self.editing_note_drawing.note, text)
            self.notebook.set_note_tags(self.editing_note_drawing.note, tags)
            self.editing_note_drawing.update_text()

        self.update_tag_menu()
        self.update_canvas_drawings()
        self.note_edit_close()

    # Close the note editor without submission.
    def note_edit_cancel(self, event=None):
        # If the note being edited does not have pre-existing text, delete it
        if self.editing_note_drawing.note.text is None:
            self.delete_note_drawing(self.editing_note_drawing)
            self.notebook.delete_note(self.editing_note_drawing.note)

        # End the note editing state
        self.note_edit_close()

    # Handle note editor's closing.
    def note_edit_close(self):
        self.editing_note_drawing = None

        self.new_button_drawing.set_state(NORMAL)
        self.notes_canvas.focus_set()
        
        # Delete the textbox for note text
        self.text_entry.delete('1.0', 'end')
        self.text_entry.config(state='disabled')
        self.notes_canvas.delete(self.text_entry_window)

        # Delete the textbox for note tags
        self.tag_entry.delete('1.0', 'end')
        self.tag_entry.config(state='disabled')
        self.notes_canvas.delete(self.tag_entry_window)

    # Handle closing of the application window.
    def on_close(self):
        if self.notebook:
            if self.editing_note_drawing:
                self.note_edit_cancel()
            self.notebook.save()
            self.notebook.save_settings()
        self.save_app_settings()
        self.root.destroy()

    # Handle mouse wheel scrolling for the notes canvas.
    def on_mouse_wheel(self, event):
        if self.notes_scrollbar.get() != (0.0, 1.0):
            self.notes_canvas.yview_scroll(-1 * (event.delta // 120), 'units')

    # Handle resizing of the notes canvas.
    def on_canvas_resize(self, event=None):
        App.CanvasDrawing.max_width = self.notes_canvas.winfo_width() - 2 * App.CANVAS_X_MARGIN

        # Update drawing widths
        for canvas_drawing in self.canvas_drawings:
            canvas_drawing.update_width()

        # Update drawing positions
        for i in range(len(self.canvas_drawings)):
            self.update_canvas_drawing_pos(i)

        self.update_scrollbar()

    # Handle clicking of the notes canvas.
    def on_canvas_click(self, event=None):
        if not self.notes_canvas.find_withtag('current'):
            self.notes_canvas.focus_set()
            if self.editing_note_drawing:
                self.note_edit_cancel()   

    # Handle clicking of note drawings.
    def on_note_drawing_click(self, note_view):
        self.note_edit_start(note_view)

        # Handle key input on the canvas
    
    # Handle clicking of tag menu items.
    def on_tag_menu_item_click(self, tag_menu_item):
        if self.editing_note_drawing:
            self.note_edit_cancel()
        tag_menu_item.on_click()
        self.update_canvas_drawings()

    # Any non-modifer key press will create a new note and open the editor for it.
    def on_key_press(self, event=None):
        ctrl_held = event.state & (1 << 2)
        if not ctrl_held and re.match('^(\w|space)$', event.keysym) and self.notebook:
            self.new_note()

    # Handle tab pressing.
    # The displayed text for every note will change to the tags of each note as long as tab is held.
    def on_tab_press(self, event=None):
        if not self.tab_held:
            self.tab_held = True
            
            for note_view in self.note_drawings:
                note_view.update_text(show_tags=True)

    # Handle tab releasing.
    # The displayed text for every note will change to the tags of each note as long as tab is held.
    def on_tab_release(self, event=None):
        self.tab_held = False

        for note_view in self.note_drawings:
            note_view.update_text(show_tags=False)

    # Handle changes to the date range specified by the DateEntry objects in the date menu.
    def on_date_menu_range_change(self, event=None):
        self.date_menu_range_start = self.date_menu_entry_start.get_date()
        self.date_menu_range_end = self.date_menu_entry_end.get_date()
        if self.notebook:
            self.update_canvas_drawings()

    # Handle changes to the date filter mode specified by the Combobox in the date menu.
    def on_date_menu_mode_change(self, event=None):
        self.notes_canvas.focus_set()
        self.update_date_menu()
        if self.editing_note_drawing:
            self.note_edit_cancel()
        if self.notebook:
            self.update_canvas_drawings()

    # STATIC - Save data into a file.
    @staticmethod
    def save_file(file, data, hidden=False, append=False):
        exists = file.exists()

        mode = os.O_WRONLY
        if not exists:
            mode = mode | os.O_CREAT
        if append:
            mode = mode | os.O_APPEND
        else:
            mode = mode | os.O_TRUNC

        with open(os.open(file, mode), 'w') as f:
            f.write(data)

        if hidden and not exists:
            os.system('attrib +h ' + file)

    # STATIC - Load data from a file.
    @staticmethod
    def load_file(file):
        if file.exists():
            with open(file, 'r') as f:
                data = f.read()
            return data
        else:
            return False
    

app = App()
