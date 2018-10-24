import os
import Queue as queue
import ctypes
import sys
import threading
import time
from collections import namedtuple
from functools import partial
from kivy import Config
from kivy import require
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

# sys.path.append(os.path.abspath(os.path.join('./pymodbuskivy')))
sys.path.append(os.path.abspath(os.path.join('./garden_graph')))

from garden_graph import Graph, MeshLinePlot

from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.transaction import ModbusRtuFramer as ModbusFramer

require('1.8.0')
Config.set('graphics', 'multisamples', '0')

Builder.load_string("""
<CustomLabel@Label>:
    size_hint: (1.0, 0.06)
    pos_hint: {'center_x': .2, 'center_y': .5}
    halign: 'left'
    text_size: self.size
    halign: 'left'
    valign: 'middle'
    name_txt: ''
    value: 0
    reg_no: 0

<CustomButton@Button>:
    size_hint: (1.0, 0.06)
    pos_hint: {'center_x': .2, 'center_y': .5}
    halign: 'left'
    text_size: self.size
    halign: 'left'
    valign: 'middle'
    name_txt: ''
    value: 0
    reg_no: 0

<Separator@Widget>
    size_hint_y: None
    thickness: 2
    margin: 2
    height: self.thickness + 2 * self.margin
    color: 155, 155, 155
    canvas:
        Color:
            rgb: self.color
        Rectangle:
            pos: self.x + self.margin, self.y + self.margin + 1
            size: self.width - 2 * self.margin , self.thickness

<LayoutApp>:
    orientation: all
    pos_hint: {'center_x': .5, 'center_y': .5}

    do_default_tab: False
    tbLiveDataLayout: _liveDataLayout
    tbChartLayout: _chartLayout
    tbDetailsLayout: detailsLayout

    TabbedPanelItem:
        text: 'Live Data'
        StackLayout:
            id: _liveDataLayout
            padding: 5
            spacing: 5

    TabbedPanelItem:
        text: 'Chart'
        BoxLayout:
            id: _chartLayout
            size_hint: 1, 1

    TabbedPanelItem:
        text: 'Heater details'
        ScrollView:
            StackLayout:
                size_hint: 1, None
                height: root.height
                id: detailsLayout
                padding: 5
                spacing: 5
""")


class Separator(Widget):
    pass


class CustomLabel(Label):
    pass


class CustomButton(Button):
    pass


class SetBox(BoxLayout):
    def __init__(self, **kwargs):
        super(SetBox, self).__init__(**kwargs)
        self.text_input = TextInput(text=str(kwargs.get('value', "")), text_align='center')
        self._btn_add = Button(text='-', on_press=self.sub_value, on_release=self.stop_update_value)
        self._btn_sub = Button(text='+', on_press=self.add_value, on_release=self.stop_update_value)
        self.add_widget(self._btn_add)
        self.add_widget(self.text_input)
        self.add_widget(self._btn_sub)

    def sub_value(self, event):
        self.event = Clock.schedule_interval(
            lambda dt: setattr(self.text_input, 'text', str(float(self.text_input.text) - 0.1)), 0.1)

    def add_value(self, event):
        self.event = Clock.schedule_interval(
            lambda dt: setattr(self.text_input, 'text', str(float(self.text_input.text) + 0.1)), 0.1)

    def get_value(self):
        return float(self.text_input.text)

    def stop_update_value(self, dt):
        self.event.cancel()


class SetPopup(Popup):
    def __init__(self, **kwargs):
        super(SetPopup, self).__init__(title_align='center', size_hint=(0.65, 0.35), **kwargs)
        self.send_callback = kwargs.get('send_callback', None)
        self.value = kwargs.get('set_val', None)
        self.reg_no = kwargs.get('reg_no', None)
        self.setup()

    def setup(self):
        content = BoxLayout(orientation='vertical', padding=15, spacing=10)
        self.set_box = SetBox(value=self.value, size_hint=(0.8, 0.15), pos_hint={'center_x': 0.5})
        btn_send = Button(text='Set', size_hint=(0.8, 0.15), pos_hint={'center_x': 0.5})
        btn_cls = Button(text='Close', size_hint=(0.8, 0.15), pos_hint={'center_x': 0.5})

        btn_send.bind(on_press=self.send)
        btn_cls.bind(on_press=self.dismiss)
        content.add_widget(self.set_box)
        content.add_widget(btn_send)
        content.add_widget(btn_cls)

        self.content = content

    def send(self, callback):
        self.dismiss()
        return self.send_callback(self.set_box.get_value(), self.reg_no)


class PlcItem():
    """Collection of all items in PLC"""

    PlcObj = namedtuple('PlcObj', 'name, reg_no, unit, factor, access')
    plc_item_dict = {
        'heater_temp': PlcObj('Temp. pieca', 1, '*C', 10, 'R'),
        'boiler_temp': PlcObj('Temp. boiler', 2, '*C', 10, 'R'),
        'l_room_temp': PlcObj('Temp. salon', 3, '*C', 10, 'R'),
        'temp_point_1': PlcObj('WZ temp komin P1', 4, '*C', 10, 'RW'),
        'heater_valve': PlcObj('Zamkniecie komina', 5, '%', 10, 'R'),
        'floor_valve': PlcObj('Zawor podlogowki', 6, '%', 10, 'RW'),
        'l_room_sp': PlcObj('WZ temp. salon', 7, '*C', 10, 'RW'),
        'l_room_delta': PlcObj('WZ delta salon', 8, '*C', 10, 'RW'),
        'temp_point_2': PlcObj('WZ temp komin P2', 9, '*C', 10, 'RW'),
        'otw_komin': PlcObj('rezerwa', 10, '*C', 10, 'R'),
        'heater_out_1': PlcObj('rezerwa', 11, '*C', 10, 'R'),
        'boiler_sp': PlcObj('WZ boiler', 12, '*C', 10, 'RW'),
        'temp_point_3': PlcObj('WZ temp komin P3', 13, '*C', 10, 'RW'),
        'temp_point_4': PlcObj('WZ temp komin P4', 14, '*C', 10, 'RW'),
        'temp_point_5': PlcObj('WZ temp komin P5', 15, '*C', 10, 'RW'),
        'th_point_1': PlcObj('WZ otw. komin P1', 16, '*C', 10, 'RW'),
        'th_point_2': PlcObj('WZ otw. komin P2', 17, '*C', 10, 'RW'),
        'th_point_3': PlcObj('WZ otw. komin P3', 18, '*C', 10, 'RW'),
        'th_point_4': PlcObj('WZ otw. komin P4', 19, '*C', 10, 'RW'),
        'th_point_5': PlcObj('WZ otw. komin P5', 20, '*C', 10, 'RW'),
        'floor_valve_sp': PlcObj('WZ temp podlogowka', 21, '*C', 10, 'RW'),
        'floor_temp': PlcObj('Temp podlogowka', 22, '*C', 10, 'R'),
        'setpoint': PlcObj('rezerwa', 23, '*C', 10, 'R'),
        'floor_valve_res': PlcObj('rezerwa', 24, '*C', 10, 'R'),
        'pid_out': PlcObj('rezerwa', 25, '*C', 10, 'R'),
        'kom_otw': PlcObj('rezerwa', 26, '*C', 10, 'R'),
        'kom_zamk': PlcObj('rezerwa', 27, '*C', 10, 'R'),
        'heater_temp_sp': PlcObj('WZ temp pieca', 28, '*C', 10, 'RW'),
        'boiler_delta': PlcObj('WZ delta boiler', 29, '*C', 10, 'RW'),
        'outdoor_temp': PlcObj('Temp. zewnetrzna', 30, '*C', 10, 'R'),
    }

    heater_dict = {
        key: value for key, value in plc_item_dict.items() if key in ['heater_temp', 'heater_temp_sp', 'floor_temp',
                                                                      'floor_valve_sp', 'floor_valve']
        }

    heater_sp_dict = {
        key: value for key, value in plc_item_dict.items() if key in ['heater_temp_sp', 'temp_point_1', 'temp_point_2',
                                                                      'temp_point_3', 'temp_point_4', 'temp_point_5',
                                                                      'th_point_1', 'th_point_2', 'th_point_3',
                                                                      'th_point_4', 'th_point_5']
        }

    boiler_dict = {
        key: value for key, value in plc_item_dict.items() if key in ['boiler_temp', 'boiler_sp', 'boiler_delta']
        }

    living_room_dict = {
        key: value for key, value in plc_item_dict.items() if key in ['l_room_temp', 'l_room_sp', 'l_room_delta']
        }

    outdoor_temp_dict = {
        key: value for key, value in plc_item_dict.items() if key in ['outdoor_temp']
        }


class ClientEngine():
    def __init__(self, **kwargs):
        self.callback = kwargs.get('callback', None)
        self.svrIp = kwargs.get('svrIp', None)
        self.svrPort = kwargs.get('svrPort', None)
        self.mbFramer = kwargs.get('mbFramer', None)
        self.client = ModbusClient(self.svrIp, port=self.svrPort, framer=self.mbFramer, timeout=1)
        self.stopper = threading.Event()
        self.queue_req = queue.LifoQueue()

    def start(self):
        self.th = threading.Thread(target=self.worker)
        self.th.start()
        self.stopper.clear()
        self.queue_req.join()

    def parse_response(self, resp, response_callback):
        if hasattr(resp, 'function_code'):
            if resp.function_code in [0x01, 0x02, 0x03, 0x04]:
                response_callback(self, resp.registers)
            elif resp.function_code in [0x06, 0x10]:
                response_callback(self)

    def worker(self):
        while not self.stopper.is_set():
            try:
                if self.client.connect():
                    while not self.queue_req.empty():
                        request, args, callback = self.queue_req.get()
                        self.parse_response(request(**args), callback)
                        self.queue_req.task_done()
                        time.sleep(0.1)
                else:
                    self.callback.on_connection_lost(self)
            except:
                print sys.exc_info()

    def _get_request_from_queue(self):
        if not self.queue_req.empty():
            request, args, callback = self.queue_req.get()
            self.parse_response(request(**args), callback)

    def read_reg(self, offset, len, response_callback):
        req = (self.client.read_holding_registers, {'address': offset, 'count': len, 'unit': 0x01}, response_callback)
        self.queue_req.put(req)

    def write_reg(self, reg_no, val, response_callback):
        req = (self.client.write_register, {'address': reg_no, 'value': val, 'unit': 0x01}, response_callback)
        self.queue_req.put(req)

    def stop(self):
        self.client.close()
        self.stopper.set()
        self.th.join()

from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window

class LayoutApp(TabbedPanel):
    """Layout of main window"""

    SAMPLES_INTERVAL_M = 5  # interval for collecting temperature samples in PLC (in minutes)
    SAMPLES_QUANTITY = 60  # number of collected samples in PLC
    SERVER_IP = '192.168.254.149'
    SERVER_PORT = 502

    # list of dicts displayed on live data tab
    LD_ITEMS_LIST = [PlcItem.heater_dict, PlcItem.boiler_dict, PlcItem.living_room_dict, PlcItem.outdoor_temp_dict]
    # list of display order on live data tab
    LD_SORT_MAP = ['outdoor_temp', 'heater_temp', 'heater_temp_sp', 'l_room_temp', 'l_room_sp', 'l_room_delta',
                   'floor_temp', 'floor_valve_sp', 'floor_valve', 'boiler_temp', 'boiler_sp', 'boiler_delta']

    # list of dicts displayed on details tab
    DETAILS_ITEMS_LIST = [PlcItem.heater_dict, PlcItem.heater_sp_dict]
    # list of display order on details tab
    DETAILS_SORT_MAP = ['heater_temp', 'heater_temp_sp', 'temp_point_1', 'temp_point_2', 'temp_point_3',
                        'temp_point_4', 'temp_point_5', 'th_point_1', 'th_point_2', 'th_point_3',
                        'th_point_4', 'th_point_5', 'floor_temp', 'floor_valve_sp', 'floor_valve']

    ld_wdgts_list = []
    details_wdgts_list = []

    def __init__(self):
        super(LayoutApp, self).__init__()
        self.plot_point_list = []
        self.comm = ClientEngine(svrIp=self.SERVER_IP, svrPort=self.SERVER_PORT, mbFramer=ModbusFramer,
                                 callback=self, timeout=0.5)
        self.comm.start()
        self.cyclic_read = None
        Clock.schedule_once(self.setup_gui)
        self.bind(current_tab=self.on_changed_tab)

    def on_changed_tab(self, instance, dt):
        if self.cyclic_read:  # previous scheduled event must be cancel before new schedule
            self.cyclic_read.cancel()

        tp_txt_name = self.get_current_tab().text
        if tp_txt_name == 'Live Data':
            self.cyclic_read = Clock.schedule_interval(self.read_live_data, 1)
        elif tp_txt_name == 'Chart':
            self.cyclic_read = Clock.schedule_interval(self.read_chart_data, 1)
        elif tp_txt_name == 'Heater details':
            self.cyclic_read = Clock.schedule_interval(self.read_details_data, 1)

    def setup_gui(self, dt):
        self._prepare_live_data_layout()
        self._prepare_chart_layout()
        self._prepare_details_layout()

    def _create_custom_widget(self, id, attributes):
        if attributes.access == 'RW':
            widget = CustomButton(text=' {}'.format(attributes.name), id=id, on_press=self.show_set_popup)
            widget.reg_no = attributes.reg_no
        else:
            widget = CustomLabel(text=' {}'.format(attributes.name), id=id)
        widget.name_txt = attributes.name
        return widget

    def _prepare_live_data_layout(self):
        for items_dict in self.LD_ITEMS_LIST:
            self.tbLiveDataLayout.add_widget(Separator())
            for key, value in sorted(items_dict.items(), key=lambda x: self.LD_SORT_MAP.index(x[0])):
                widget = self._create_custom_widget(key, value)
                self.ld_wdgts_list.append(widget)
                self.tbLiveDataLayout.add_widget(widget)
        self.tbLiveDataLayout.add_widget(Separator())
        self.cyclic_read = Clock.schedule_interval(self.read_live_data, 1)

    def _prepare_chart_layout(self):
        x_min = -1 * self.SAMPLES_INTERVAL_M * self.SAMPLES_QUANTITY
        self.x_points = range(x_min, 0, self.SAMPLES_INTERVAL_M)

        self.graph = Graph(xlabel='Last minutes', ylabel='Temperature [C]', x_ticks_minor=5,
                           x_ticks_major=25, y_ticks_major=10, y_ticks_minor=5,
                           y_grid_label=True, x_grid_label=True, padding=5,
                           x_grid=True, y_grid=True, ymin=0, ymax=100, xmin=x_min, xmax=0,
                           pos_hint={'center_x': .5, 'center_y': .5}
                           )
        self.plot = MeshLinePlot(color=[0, 1, 0, 1])
        self.graph.add_plot(self.plot)
        self.tbChartLayout.add_widget(self.graph)

    def _prepare_details_layout(self):
        for items_dict in self.DETAILS_ITEMS_LIST:
            self.tbDetailsLayout.add_widget(Separator())
            for key, value in sorted(items_dict.items(), key=lambda x: self.DETAILS_SORT_MAP.index(x[0])):
                widget = self._create_custom_widget(key, value)
                self.details_wdgts_list.append(widget)
                self.tbDetailsLayout.add_widget(widget)
        self.tbDetailsLayout.add_widget(Separator())


    def show_set_popup(self, instance):
        popup = SetPopup(title=instance.name_txt, set_val=instance.value, send_callback=self.write_reg,
                         reg_no=instance.reg_no)
        popup.open()

    def _update_widget(self, widget, plc_item, value):
        widget.value = value
        widget.text = ' {} = {}{}'.format(plc_item.name, value, plc_item.unit)

    def _fill_main_window_widgets(self, data, dt):
        for widget in self.ld_wdgts_list:
            plc_item = filter(lambda x: x.get(widget.id), self.LD_ITEMS_LIST)[0][widget.id]
            value = (float(ctypes.c_short(data[plc_item.reg_no]).value) / plc_item.factor)
            self._update_widget(widget, plc_item, value)

    def _update_plot_points(self, data, dt):
        self.plot_point_list = []
        for val in data:
            self.plot_point_list.append(float(val / 10))
        self.plot_point_list.reverse()
        self.plot.points = zip(self.x_points, self.plot_point_list)

    def _fill_details_widgets(self, data, dt):
        for widget in self.details_wdgts_list:
            plc_item = filter(lambda x: x.get(widget.id), self.DETAILS_ITEMS_LIST)[0][widget.id]
            value = (float(ctypes.c_short(data[plc_item.reg_no]).value) / plc_item.factor)
            self._update_widget(widget, plc_item, value)

    def stop(self):
        self.comm.stop()

    def on_connection_lost(self, inst):
        print "lost connection"

    def read_live_data(self, inst):
        self.comm.read_reg(0, 32, self.on_resp_live_data)

    def read_details_data(self, inst):
        self.comm.read_reg(0, 32, self.on_resp_details_data)

    def on_resp_live_data(self, inst, data):
        Clock.schedule_once(partial(self._fill_main_window_widgets, data), 0)

    def on_resp_details_data(self, inst, data):
        Clock.schedule_once(partial(self._fill_details_widgets, data), 0)

    def read_chart_data(self, inst):
        self.comm.read_reg(129, 60, self.on_resp_chart_data)

    def on_resp_chart_data(self, inst, data):
        Clock.schedule_once(partial(self._update_plot_points, data), 0)

    def write_reg(self, val, reg_no):
        self.comm.write_reg(reg_no, int(val * 10), self.on_write_reg)

    def on_write_reg(self, inst):
        pass


class KvHome(App):
    """Main app window"""
    layout = LayoutApp()

    def build(self):
        return self.layout

    def on_pause(self):
        return True

    def on_stop(self):
        self.layout.stop()


if __name__ in ('__main__', '__android__'):
    KvHome().run()
