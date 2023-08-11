import datetime as dt
import pathlib
import socket as sk
import sys
import tkinter as tk
import webbrowser

from tkinter import ttk, filedialog, messagebox

import PIL
import PIL.Image
import PIL.ImageFile
import PIL.ImageTk

from GeoscanDecoder import AGWPE_CON
from GeoscanDecoder.geoscan import geoscan, GeoscanImageReceiver
from GeoscanDecoder.version import __version__


PIL.ImageFile.LOAD_TRUNCATED_IMAGES = 1


class App(ttk.Frame):
    def __init__(self, config):
        super().__init__()

        self.config = config
        self.sk = 0
        self.ir = GeoscanImageReceiver(config.get('main', 'outdir'))

        self.master.protocol("WM_DELETE_WINDOW", self.exit)
        self.master.option_add('*tearOff', tk.FALSE)
        self.master.title('Geoscan-Edelveis decoder')
        # self.master.columnconfigure(0, weight=1)
        # self.master.rowconfigure(0, weight=1)

        self.grid(column=0, row=0, sticky=tk.NSEW)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.master.bind('<Control-Q>', self.exit)
        self.master.bind('<Control-q>', self.exit)
        self.master.bind('<F1>', self.about)

        # canvas frame
        self.canvas_frame = ttk.LabelFrame(self, text='Image', padding=(3, 3, 3, 3))
        self.canvas_frame.grid(column=0, rowspan=2, row=0, sticky=tk.NSEW, padx=2, pady=2)
        self.canvas_frame.rowconfigure(1, weight=1)

        self.image_starter = ttk.Label(self.canvas_frame, text='STARTER', foreground='red')
        self.image_starter.grid(column=0, row=0, sticky=tk.E, padx=0)

        self.image_soi = ttk.Label(self.canvas_frame, text='SOI', foreground='red')
        self.image_soi.grid(column=1, row=0, sticky=tk.E, padx=0)

        self.image_offset_l = ttk.Label(self.canvas_frame, text='Base offset:')
        self.image_offset_l.grid(column=2, row=0, sticky=tk.E, padx=0)

        self.image_offset_v = tk.IntVar(self.canvas_frame, self.ir.BASE_OFFSET)
        self.image_offset = ttk.Entry(self.canvas_frame, textvariable=self.image_offset_v, width=7,
                                      validate='all', validatecommand=lambda: False)
        self.image_offset.grid(column=3, row=0, sticky=tk.W, padx=0)

        self.canvas_sz = 420, 420
        self.canvas = tk.Canvas(self.canvas_frame, width=self.canvas_sz[0], height=self.canvas_sz[1])
        self.canvas.grid(columnspan=4, sticky=tk.NSEW, pady=3)

        self.image_name_l = ttk.Label(self.canvas_frame)
        self.image_name_l.grid(columnspan=4, sticky=tk.SW, pady=3)

        # ctrl frame
        self.ctrl_frame = ttk.LabelFrame(self, text='Options', padding=(3, 3, 3, 3))
        self.ctrl_frame.grid(column=1, row=0, sticky=tk.NSEW, padx=2, pady=2)
        self.ctrl_frame.columnconfigure(1, weight=1)
        self.ctrl_frame.columnconfigure(4, weight=1)

        self.out_dir_v = tk.StringVar(self.ctrl_frame, config.get('main', 'outdir'), 'Out dir')
        self.out_dir_e = ttk.Entry(self.ctrl_frame, textvariable=self.out_dir_v, state=tk.NORMAL)
        self.out_dir_e.grid(column=0, columnspan=4, row=0, sticky=tk.EW, pady=3)

        self.out_dir_btn = ttk.Button(self.ctrl_frame, text='Out Dir', command=self.set_out_dir)
        self.out_dir_btn.grid(column=4, row=0, sticky=tk.EW, pady=3, padx=3)

        self.server_v = tk.StringVar(self.ctrl_frame, self.config.get('main', 'ip'), 'Server')
        self.port_v = tk.StringVar(self.ctrl_frame, self.config.get('main', 'port'), 'Port')

        ttk.Label(self.ctrl_frame, text='Server:').grid(column=0, row=1, sticky=tk.E, pady=3)
        self.server_e = ttk.Entry(self.ctrl_frame, textvariable=self.server_v)
        self.server_e.grid(column=1, row=1, sticky=tk.EW, pady=3)

        ttk.Label(self.ctrl_frame, text='Port:').grid(column=2, row=1, sticky=tk.E, pady=3)
        self.port_e = ttk.Entry(self.ctrl_frame, textvariable=self.port_v, width=7)
        self.port_e.grid(column=3, row=1, sticky=tk.EW, pady=3)

        self.con_btn = ttk.Button(self.ctrl_frame, text='Connect', command=self.con)
        self.con_btn.grid(column=4, row=1, sticky=tk.EW, pady=3, padx=3)

        self.merge_mode_v = tk.IntVar(self.ctrl_frame, self.config.getboolean('main', 'merge mode'), 'Merge mode')
        self.merge_mode_ckb = ttk.Checkbutton(self.ctrl_frame, text='Merge mode',
                                              variable=self.merge_mode_v, command=self.set_merge_mode)
        self.merge_mode_ckb.grid(column=2, columnspan=2, row=2, sticky=tk.EW, pady=3)

        self.new_btn = ttk.Button(self.ctrl_frame, text='New image', command=self.new_img)
        self.new_btn.grid(column=4, row=2, sticky=tk.EW, pady=3, padx=3)

        # tlm frame
        self.tlm_frame = ttk.LabelFrame(self, text='Telemetry', padding=(3, 3, 3, 3))
        self.tlm_frame.grid(column=1, row=1, sticky=tk.NSEW, padx=2, pady=2)

        self.tlm_table = ttk.Treeview(self.tlm_frame, columns='x val', height=17, selectmode='browse', show='tree')
        self.tlm_table.column('#0', anchor='e')
        self.tlm_table.column('x', width=0)

        self.tlm_table.insert('', 'end', 'time', text='Time')
        self.tlm_table.insert('', 'end', 'Iab', text='Current total, A')
        self.tlm_table.insert('', 'end', 'Isp', text='Current SP, A')
        self.tlm_table.insert('', 'end', 'Uab_per', text='Voltage per battery, V')
        self.tlm_table.insert('', 'end', 'Uab_sum', text='Voltage total, V')
        self.tlm_table.insert('', 'end', 'Tx_plus', text='Temperature SP X+, °C')
        self.tlm_table.insert('', 'end', 'Tx_minus', text='Temperature SP X-, °C')
        self.tlm_table.insert('', 'end', 'Ty_plus', text='Temperature SP Y+, °C')
        self.tlm_table.insert('', 'end', 'Ty_minus', text='Temperature SP Y-, °C')
        self.tlm_table.insert('', 'end', 'Tz_plus', text='Temperature SP Z+, °C')
        self.tlm_table.insert('', 'end', 'Tz_minus', text='Temperature SP Z-, °C')
        self.tlm_table.insert('', 'end', 'Tab1', text='Temperature battery 1, °C')
        self.tlm_table.insert('', 'end', 'Tab2', text='Temperature battery 2, °C')
        self.tlm_table.insert('', 'end', 'CPU_load', text='CPU load, %')
        self.tlm_table.insert('', 'end', 'Nres_osc', text='Reloads spacecraft')
        self.tlm_table.insert('', 'end', 'Nres_CommU', text='Reloads CommU')
        self.tlm_table.insert('', 'end', 'RSSI', text='RSSI')

        self.tlm_table.grid(sticky=tk.NSEW, pady=3)

        self.tlm_name_l = ttk.Label(self.tlm_frame)
        self.tlm_name_l.grid(sticky=tk.EW, pady=3)

        #####
        self.update()
        self.master.minsize(self.winfo_width(), self.winfo_height())

    def exit(self, evt=None):
        if self.sk:
            self._stop()

        self.config.set('main', 'ip', self.server_v.get())
        self.config.set('main', 'port', self.port_v.get())
        self.config.set('main', 'outdir', self.out_dir_v.get())
        self.config.set('main', 'merge mode', str(self.merge_mode_v.get()))

        self.quit()

    def about(self, evt=None):
        about = tk.Toplevel(self)
        about.title('About')

        frame = ttk.Frame(about, padding=(3, 3, 3, 3))
        frame.grid(column=0, row=0, sticky=tk.NSEW)

        ttk.Label(frame, text=f'GeoscanDecoder v{__version__}').grid(columnspan=2)
        ttk.Label(frame, text='MIT License\nCopyright (c) 2023 Alexander Baskikh\n', justify='center').grid(columnspan=2, rowspan=3)

        ttk.Label(frame, text='GitHub page:').grid(column=0, row=4, sticky=tk.E)
        link = 'https://github.com/baskiton/GeoscanDecoder'
        x = ttk.Label(frame, text=link, foreground='blue', cursor='hand2')
        x.bind('<Button-1>', lambda e: webbrowser.open(link))
        x.grid(column=1, row=4, sticky=tk.W)

        ttk.Label(frame, text='Geoscan page:').grid(column=0, row=5, sticky=tk.E)
        link = 'https://geoscan.space/ru/geoscan-edelveis'
        x = ttk.Label(frame, text=link, foreground='blue', cursor='hand2')
        x.bind('<Button-1>', lambda e: webbrowser.open(link))
        x.grid(column=1, row=5, sticky=tk.W)

        ttk.Label(frame, text='Amateurs chat:').grid(column=0, row=6, sticky=tk.E)
        link = 'https://t.me/amateursat'
        x = ttk.Label(frame, text=link, foreground='blue', cursor='hand2')
        x.bind('<Button-1>', lambda e: webbrowser.open(link))
        x.grid(column=1, row=6, sticky=tk.W)

        ttk.Button(frame, text='Ok', command=lambda: (about.grab_release(), about.destroy())).grid(columnspan=2)

        about.transient(self)
        about.wait_visibility()
        about.grab_set()

        about.update()
        about.minsize(frame.winfo_width(), frame.winfo_height())
        about.maxsize(frame.winfo_width(), frame.winfo_height())

    def con(self):
        self._stop() if self.sk else self._start()

    def _start(self):
        try:
            s = sk.socket(sk.AF_INET, sk.SOCK_STREAM)
            s.connect((self.server_v.get(), int(self.port_v.get())))
            s.settimeout(0.1)

            self.sk = s
            self.sk.send(AGWPE_CON)

        except (ConnectionError, OSError) as e:
            messagebox.showerror(message=e.strerror)

        except Exception as e:
            messagebox.showerror(message=str(e.args))

        else:
            self.con_btn.config(text='Disconnect')
            self.server_e.config(state=tk.DISABLED)
            self.port_e.config(state=tk.DISABLED)
            self.out_dir_e.config(state=tk.DISABLED)
            self.out_dir_btn.config(state=tk.DISABLED)
            self.update()

            self.ir.set_outdir(self.out_dir_v.get())
            self.ir.set_merge_mode(self.merge_mode_v.get())
            try:
                self._receive()
            except Exception as e:
                messagebox.showerror(message=str(e.args))
                self._stop()

    def _stop(self):
        if self.sk:
            s = self.sk
            self.sk = 0
            s.close()

        self.con_btn.config(text='Connect')
        self.server_e.config(state=tk.NORMAL)
        self.port_e.config(state=tk.NORMAL)
        self.out_dir_e.config(state=tk.NORMAL)
        self.out_dir_btn.config(state=tk.NORMAL)
        self.update()

    def set_out_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.out_dir_v.set(d)

    def set_merge_mode(self):
        self.ir.set_merge_mode(self.merge_mode_v.get())

    def _receive(self):
        cur_img_name = None

        while self.sk:
            try:
                frame = self.sk.recv(4096)
            except (sk.timeout, TimeoutError):
                continue
            finally:
                self.update()

            if not frame:
                messagebox.showwarning(message='Connection lost')
                self._stop()
                return

            data = frame[37:]
            tlm = geoscan.parse(data)
            if tlm.geoscan:
                geo_tlm = tlm.geoscan
                self._fill_telemetry(geo_tlm)
                fp = pathlib.Path(self.out_dir_v.get()) / f'GEOSCAN_{dt.datetime.now()}.txt'.replace(' ', '_').replace(':', '-')
                self.tlm_name_l.config(text=fp.name)

                with fp.open('w') as f:
                    if sys.version_info < (3, 8, 0):
                        f.write(data.hex())
                    else:
                        f.write(data.hex(' '))
                    f.write('\n\n')
                    f.write(str(geo_tlm))

            x = self.ir.push_data(data)
            if x:
                if x == 1:
                    f = self.ir.files.get(self.ir.current_fid)
                    if f:
                        cur_img_name = f.name
                        self.image_name_l.config(text=pathlib.Path(cur_img_name).name)
                self._fill_canvas(cur_img_name)

    def _fill_canvas(self, fname):
        self.image_starter.config(foreground=self.ir.has_starter and 'green' or 'red')
        self.image_soi.config(foreground=self.ir.has_soi and 'green' or 'red')
        self.image_offset_v.set(self.ir.base_offset)
        i = None
        try:
            i = PIL.Image.open(fname)
            self.canvas.delete(tk.ALL)
            if i.size != self.canvas_sz:
                self.canvas.config(width=i.width, height=i.height)
                self.canvas_sz = i.size
                self.canvas.update()
                self.master.minsize(self.winfo_width(), self.winfo_height())
            self._imgtk = PIL.ImageTk.PhotoImage(i)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self._imgtk)

        except:
            pass

        if i:
            i.close()

    def _fill_telemetry(self, tlm):
        self.tlm_table.set('time', 'val', tlm.time)
        self.tlm_table.set('Iab', 'val', tlm.Iab)
        self.tlm_table.set('Isp', 'val', tlm.Isp)
        self.tlm_table.set('Uab_per', 'val', tlm.Uab_per)
        self.tlm_table.set('Uab_sum', 'val', tlm.Uab_sum)
        self.tlm_table.set('Tx_plus', 'val', tlm.Tx_plus)
        self.tlm_table.set('Tx_minus', 'val', tlm.Tx_minus)
        self.tlm_table.set('Ty_plus', 'val', tlm.Ty_plus)
        self.tlm_table.set('Ty_minus', 'val', tlm.Ty_minus)
        self.tlm_table.set('Tz_plus', 'val', tlm.Tz_plus)
        self.tlm_table.set('Tz_minus', 'val', tlm.Tz_minus)
        self.tlm_table.set('Tab1', 'val', tlm.Tab1)
        self.tlm_table.set('Tab2', 'val', tlm.Tab2)
        self.tlm_table.set('CPU_load', 'val', tlm.CPU_load)
        self.tlm_table.set('Nres_osc', 'val', tlm.Nres_osc)
        self.tlm_table.set('Nres_CommU', 'val', tlm.Nres_CommU)
        self.tlm_table.set('RSSI', 'val', tlm.RSSI)

    def new_img(self):
        self.canvas.delete(tk.ALL)
        self.ir.force_new()
        self.image_name_l.config(text=pathlib.Path(self.ir.files.get(self.ir.current_fid).name).name)

        self.image_starter.config(foreground='red')
        self.image_soi.config(foreground='red')
        self.image_offset_v.set(self.ir.BASE_OFFSET)
