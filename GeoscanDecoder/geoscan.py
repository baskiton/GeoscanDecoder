import datetime as dt
import pathlib

import construct


ssid = construct.BitStruct(
    "ch" / construct.Flag,  # C / H bit
    construct.Default(construct.BitsInteger(2), 3),  # reserved bits
    "ssid" / construct.BitsInteger(4),
    "extension" / construct.Flag,  # last address bit
)


class CallsignAdapter(construct.Adapter):
    def _encode(self, obj, context, path=None):
        return bytes(
            [x << 1 for x in bytes((obj.upper() + " " * 6)[:6], encoding="ascii")]
        )

    def _decode(self, obj, context, path=None):
        return str(bytes([x >> 1 for x in obj]), encoding="ascii").strip()


class UNIXTimestampAdapter(construct.Adapter):
    def _encode(self, obj, context, path=None):
        return round(obj.timestamp())

    def _decode(self, obj, context, path=None):
        return dt.datetime.utcfromtimestamp(obj)


callsign = CallsignAdapter(construct.Bytes(6))

address = construct.Struct("callsign" / callsign, "ssid" / ssid)

control = construct.Hex(construct.Int8ub)

pid = construct.Hex(construct.Int8ub)

ax25_header = construct.Struct(
    "addresses" / construct.RepeatUntil(lambda x, lst, ctx: x.ssid.extension, address),
    "control" / control,
    "pid" / pid,
)

ax25 = construct.Struct("header" / ax25_header, "info" / construct.GreedyBytes)


# GEOSCAN Telemetry Protocol
# https://download.geoscan.aero/site-files/%D0%9F%D1%80%D0%BE%D1%82%D0%BE%D0%BA%D0%BE%D0%BB%20%D0%BF%D0%B5%D1%80%D0%B5%D0%B4%D0%B0%D1%87%D0%B8%20%D1%82%D0%B5%D0%BB%D0%B5%D0%BC%D0%B5%D1%82%D1%80%D0%B8%D0%B8.pdf
# (https://download.geoscan.aero/site-files/Протокол передачи телеметрии.pdf)


class SubAdapter(construct.Adapter):
    def __init__(self, v, *args, **kwargs):
        self.v = v
        construct.Adapter.__init__(self, *args, **kwargs)

    def _encode(self, obj, context, path=None):
        return int(obj + self.v)

    def _decode(self, obj, context, path=None):
        return obj - self.v


class MulAdapter(construct.Adapter):
    def __init__(self, v, *args, **kwargs):
        self.v = v
        construct.Adapter.__init__(self, *args, **kwargs)

    def _encode(self, obj, context, path=None):
        return int(round(obj / self.v))

    def _decode(self, obj, context, path=None):
        return float(obj) * self.v


geoscan_frame = construct.Struct(
    "time" / UNIXTimestampAdapter(construct.Int32ul),
    "Iab" / MulAdapter(0.0766, construct.Int16ul),  # mA
    "Isp" / MulAdapter(0.03076, construct.Int16ul),  # mA
    "Uab_per" / MulAdapter(0.00006928, construct.Int16ul),  # V
    "Uab_sum" / MulAdapter(0.00013856, construct.Int16ul),  # V
    "Tx_plus" / construct.Int8ul,  # deg C
    "Tx_minus" / construct.Int8ul,  # deg C
    "Ty_plus" / construct.Int8ul,  # deg C
    "Ty_minus" / construct.Int8ul,  # deg C
    "Tz_plus" / construct.Int8ul,  # undef
    "Tz_minus" / construct.Int8ul,  # deg C
    "Tab1" / construct.Int8ul,  # deg C
    "Tab2" / construct.Int8ul,  # deg C
    "CPU_load" / construct.Int8ul,  # %
    "Nres_osc" / SubAdapter(7476, construct.Int16ul),
    "Nres_CommU" / SubAdapter(1505, construct.Int16ul),
    "RSSI" / SubAdapter(99, construct.Int8ul),  # dBm
    "pad" / construct.GreedyBytes,
)

geoscan = construct.Struct(
    "ax25" / construct.Peek(ax25_header),
    "ax25"
    / construct.If(
        lambda this: (bool(this.ax25) and this.ax25.addresses[0].callsign == "BEACON"),
        ax25_header,
    ),
    "geoscan"
    / construct.If(
        lambda this: (bool(this.ax25) and this.ax25.pid == 0xF0), geoscan_frame
    ),
)


_frame = construct.Struct(
    "marker" / construct.Int16ul,  # #0
    "dlen" / construct.Int8ul,  # #2
    "mtype" / construct.Int16ul,  # #3
    "offset" / construct.Int16ul,  # #5
    "subsystem_num" / construct.Int8ul,  # #7
    "data" / construct.Bytes(construct.this.dlen - 6)
    # 'data' / construct.Bytes(56)
)


class GeoscanImageReceiver:
    MARKER_IMG = 0x0001
    CMD_IMG_START = 0x0901
    CMD_IMG_FRAME = 0x0905
    BASE_OFFSET = 0  # old 4     # old 16384     # old 32768

    def __init__(self, outdir):
        self.outdir = pathlib.Path(outdir).expanduser().absolute()
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.files = {}
        self.merge_mode = 0
        self.base_offset = self.BASE_OFFSET
        self.has_starter = self.has_soi = 0
        self.current_fid = None
        self._prev_data_sz = -1
        self._miss_cnt = 0

    def set_outdir(self, outdir):
        self.outdir = pathlib.Path(outdir).expanduser().absolute()
        self.outdir.mkdir(parents=True, exist_ok=True)

    def set_merge_mode(self, val):
        self.merge_mode = val

    def generate_fid(self):
        if not (self.current_fid and self.merge_mode):
            self.current_fid = f"GEOSCAN_{dt.datetime.now()}".replace(" ", "_").replace(
                ":", "-"
            )
        return self.current_fid

    def force_new(self):
        f = self.files.get(self.current_fid)
        if f:
            f.close()
        self.has_starter = self.has_soi = self.current_fid = 0
        self.new_file(self.generate_fid())

    def new_file(self, fid):
        fn = self.outdir / (fid + ".jpg")
        f = open(fn, "w+b")
        self.files[fid] = f
        return f

    def push_data(self, data):
        data = self.parse_data(data)
        if not data:
            return

        # fid = self.file_id(data)
        fid = self.current_fid or self.generate_fid()
        if not fid:
            fid = self.current_fid

        f = self.files.get(fid)
        if not f:
            f = self.new_file(fid)

        self.current_fid = fid

        f.seek(data.offset)
        f.write(data.data)
        f.flush()

        if self.is_last_data(data) and not self.merge_mode:
            f.close()
            self.current_fid = None
            self.base_offset = self.BASE_OFFSET
            self.has_starter = self.has_soi = 0
            return 2

        return 1

    def parse_data(self, data):
        try:
            data = _frame.parse(data)
        except construct.ConstructError:
            return

        if data.marker != self.MARKER_IMG:
            self._miss_cnt += 1
            return

        if data.mtype == self.CMD_IMG_START:
            if data.data.startswith(b"\xff\xd8"):
                self.has_soi = data.offset
            self.has_starter = 1
            self.base_offset = data.offset
            data.offset = 0
            self.generate_fid()

        elif data.mtype == self.CMD_IMG_FRAME:
            if (
                not self.has_starter
                and not self.has_soi
                and data.data.startswith(b"\xff\xd8")
            ):
                self.base_offset = data.offset
                self.has_soi = data.offset
                self.generate_fid()

            x = data.offset - self.base_offset
            if x < 0:
                self.force_new()
                self.base_offset = self.BASE_OFFSET
                x = data.offset - self.base_offset
            data.offset = x

        else:
            return

        return data

    def is_last_data(self, data):
        prev_sz = self._prev_data_sz
        self._prev_data_sz = len(data.data)
        return (self._prev_data_sz < prev_sz) and b"\xff\xd9" in data.data
