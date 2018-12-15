import tkinter as tk
import tkinter.ttk as ttk
import tkinter.scrolledtext as tkst
import collections
import logging
import queue

logger = logging.getLogger(__name__)


class Vui:

    def __init__(self,  master, type_list, device_id):
        self.master = master
        self.master.title("Virtual Device v??")
        self.device_id = device_id
        self.vdev_update = None
        self.create_device_table(type_list, device_id)

        self.access_queue = queue.Queue()

        self.build_ui()
        self._update_from_queue()

    def set_vdev_update_function(self, update_func):
        self.vdev_update = update_func

    def create_device_table(self, type_list, device_id):
        self.device_id = device_id
        self.device = collections.OrderedDict()

        for field in type_list:
            data_name, data_type = field['name'], field['type']
            items = []
            if isinstance(data_type, list):
                items= data_type
                data_type = 'Enum'
            
            value_var = tk.StringVar()
            update_var = tk.BooleanVar()
            bool_var = tk.BooleanVar()
            self.device[data_name] = dict(data_type=data_type, items=items, value_var=value_var, update_var=update_var, bool_var=bool_var)

    def _build_data_field_ui(self, frame):
        row = 0
        for name, info in self.device.items():
            data_frame = tk.LabelFrame(frame, text=name)
            data_frame.grid(row=row, column=0, sticky='NSEW')


            if info['data_type']=='Enum':
                info['value_var'].set(info['items'][0])
                entry = ttk.Combobox(data_frame, values=info['items'], textvariable=info['value_var'], state="readonly")
            elif info['data_type']=='Boolean':
                entry = ttk.Checkbutton(data_frame, variable=info['bool_var'], text='{} value'.format(name))
            else:
                entry = ttk.Entry(data_frame, textvariable=info['value_var'])
                pass

            entry.grid(row=0,column=0,sticky='NSEW')
 
            tk.Checkbutton(data_frame, text='',variable=info['update_var'],command=self.allow_update_change).grid(row=0, column=2)
            tk.Button(data_frame, text='Send', command=lambda name=name:self.field_update_button_click(name)).grid(row=0, column=1)

            data_frame.grid_columnconfigure(0,weight=1)
            row = row+1

    def allow_update_change(self):
        allow = tk.DISABLED
        for _, info in self.device.items():
            if info['update_var'].get():
                allow = tk.NORMAL
                break
        
        
        self.send_all_button.configure(state=allow)

    def config_log_widget(self):
        self.log_view.config(state='disabled')
        self.log_view.tag_config("INFO", foreground="black")
        self.log_view.tag_config("DEBUG", foreground="grey")
        self.log_view.tag_config("WARNING", foreground="orange")
        self.log_view.tag_config("ERROR", foreground="red")
        self.log_view.tag_config("CRITICAL", foreground="red", underline=1)        
        

    def build_ui(self):
        top_frame = tk.Frame(self.master)
        
        top_frame.grid(row=0, column=0, sticky='NSEW')

        tk.Label(top_frame, text='VDev device-id={}'.format(self.device_id)).grid(row=0, column=0,sticky='NSEW')
        
        data_frame = tk.Frame(self.master)
        data_frame.grid(row=1,column=0, sticky='NSEW')

        self._build_data_field_ui(data_frame)
        
        self.send_all_button = tk.Button(data_frame, text='Send\nSelected', state=tk.DISABLED, command=self.all_fields_update_button_click)

        self.send_all_button.grid(row=0, column=1, rowspan=len(self.device), sticky='NSEW')

        log_frame = tk.LabelFrame(self.master, text='Log')
        log_frame.grid(row=2,column=0, sticky='NSEW')

        log_view = tkst.ScrolledText(log_frame,wrap='word')
        log_view.grid(row=0,column=0,sticky='NSEW')
        self.log_view = log_view
        self.config_log_widget()

        self.master.grid_columnconfigure(0, weight=1)
        self.master.grid_rowconfigure(0, weight=0)
        self.master.grid_rowconfigure(1, weight=0)
        self.master.grid_rowconfigure(2, weight=1)

        log_frame.grid_columnconfigure(0,weight=1)
        log_frame.grid_rowconfigure(0,weight=1)

        top_frame.grid_columnconfigure(0,weight=1)

        data_frame.grid_columnconfigure(0,weight=10)
        data_frame.grid_columnconfigure(1,weight=1)

    def all_fields_update_button_click(self):
        ret = {}

        for name, info in self.device.items():
            allow_send = info['update_var'].get()

            if allow_send:
                value = self._get_data_field_value(name)
                if value != None:
                    ret[name]=value

            x = self._get_data_field_value(name)
        
        if ret:
            self.update_platform(ret)

    def _get_data_field_value(self, name):
        field_type = self.device[name]['data_type']

        field_str = self.device[name]['value_var'].get()

        if field_type == 'Number':
            try:
                v = int(field_str)
            except:
                try:
                    v = float(field_str)
                except:
                    logger.error('Except number for {}'.format(name))
                    return None
            return v
        elif field_type == 'Boolean':
            return self.device[name]['bool_var'].get()
        else:
            return field_str

    def field_update_button_click(self, name):
        value = self._get_data_field_value(name)
        if value != None:
            self.update_platform({name:value})

    def update_with_data_dic(self, data_dic):
        self.access_queue.put(('data', data_dic))

    
    def _update_ui_from_data_dic(self, data_dic_list):
        data_dic = {}
        for x in data_dic_list:
            data_dic.update(x)

        for name, value in data_dic.items():
            field_info = self.device[name]

            if field_info['data_type'] == 'Boolean':
                field_info['bool_var'].set(value)
            else:
                field_info['value_var'].set(str(value))

    def _update_from_queue(self):
        data_list = []
        log_list = []

        while True:
            try:
                (cmd, value) = self.access_queue.get(timeout=0)
                if cmd == 'data':
                    data_list.append(value)
                elif cmd == 'log':
                    log_list.append(value)
            except queue.Empty:
                break

        
        if data_list:
            self._update_ui_from_data_dic(data_list)
        
        if log_list:
            self._update_log_record(log_list)

        self.master.after(100, self._update_from_queue)
        
    
    def _update_log_record(self, log_list):
        self.log_view.config(state='normal')
        # Append message (record) to the widget

        for text, levelname in log_list:
            self.log_view.insert(tk.END, text + '\n', levelname)

        self.log_view.see(tk.END)  # Scroll to the bottom
        self.log_view.config(state='disabled') 
        self.log_view.update() # Refresh the widget
       

    def update_platform(self, update_dict):
        #print(update_dict)
        if self.vdev_update:
            self.vdev_update(update_dict)

    def get_logger(self):
        return WidgetLogger(self.access_queue)

        
class WidgetLogger(logging.Handler):
    def __init__(self, target_queue):
        logging.Handler.__init__(self)
        self.setLevel(logging.DEBUG)
        self.q = target_queue

    def emit(self, record):
        self.q.put(('log', (self.format(record), record.levelname )))

