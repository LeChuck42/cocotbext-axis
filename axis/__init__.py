from cocotb.decorators import coroutine
from cocotb.triggers import RisingEdge, ReadOnly, Event
from cocotb.drivers import ValidatedBusDriver
from cocotb.monitors import BusMonitor
from cocotb.binary import BinaryValue, resolve

class AXIS_ProtocolError(Exception):
    pass

class AXIS_Master(ValidatedBusDriver):
    """AXI Stream Master Interface Driver"""

    _signals = ["tvalid"]
    _optional_signals = ["tdata", "tkeep", "tready", "tlast", "tstrb", "tid",
                         "tdest", "tuser"]

    def __init__(self, entity, name, clock, lsb_first=True, **kwargs):
        ValidatedBusDriver.__init__(self, entity, name, clock, **kwargs)
        if hasattr(self.bus, 'tdata'):
            self._n_bytes, rem = divmod(len(self.bus.tdata), 8)
            if rem:
                raise AttributeError("tdata width has to be multiple of 8")
        else:
            self._n_bytes = 1

        self._lsb_first = lsb_first
        self._idle_outputs()

    def _idle_outputs(self):
        # Drive default values
        self.bus.tvalid <= 0
        if hasattr(self.bus, 'tdata'):
            self.bus.tdata <= BinaryValue("x"*len(self.bus.tdata))
        if hasattr(self.bus, 'tlast'):
            self.bus.tlast <= BinaryValue('x')
        if hasattr(self.bus, 'tkeep'):
            self.bus.tkeep <= BinaryValue("x"*self._n_bytes)
        if hasattr(self.bus, 'tstrb'):
            self.bus.tstrb <= BinaryValue("x"*self._n_bytes)
        if hasattr(self.bus, 'tid'):
            self.bus.tid <= BinaryValue("x"*len(self.bus.tid))
        if hasattr(self.bus, 'tdest'):
            self.bus.tdest <= BinaryValue("x"*len(self.bus.tdest))
        if hasattr(self.bus, 'tuser'):
            self.bus.tuser <= BinaryValue("x"*len(self.bus.tuser))

    @coroutine
    def _send_bytes(self, bytestr, padZero=False, tid=None, tdest=None, tuser=None):
        """Send a byte-like object on the AXI stream

        Args:
            bytestr (byte-like): data to be sent
            padZero (boolean): pad the data stream with zero bits instead of 'X'
            tid:
            tdest:
            tuser:
        """
        if padZero:
            padstr = "00000000"
        else:
            padstr = "XXXXXXXX"

        bytestr = bytes(bytestr)

        for offset in range(0, len(bytestr), self._n_bytes):

            if offset+self._n_bytes < len(bytestr):
                last_word = 0
                padbytes = 0
            else:
                last_word = 1
                padbytes = offset+self._n_bytes - len(bytestr)

            if not self.on:
                self.bus.tdata <= BinaryValue(padstr*self._n_bytes)
                self.bus.tvalid <= 0
                for _ in range(self.off):
                    yield RisingEdge(self.clock)
                self._next_valids()

            # Consume a valid cycle
            if self.on is not True and self.on:
                self.on -= 1

            self.bus.tvalid <= 1

            if hasattr(self.bus, 'tlast'):
                self.bus.tlast <= last_word

            bytelist = list(bytestr[offset:offset+self._n_bytes])

            if self._lsb_first:
                bytelist.reverse()

            binstr = ''.join(map(lambda b: "{:08b}".format(b), bytelist))

            if padbytes:
                if self._lsb_first:
                    binstr = padstr*padbytes + binstr
                    keepstr = "0"*padbytes + "1"*(self._n_bytes-padbytes)
                else:
                    binstr = binstr + padstr*padbytes
                    keepstr = "1"*(self._n_bytes-padbytes) + "0"*padbytes
            else:
                keepstr = "1"*self._n_bytes

            self.bus.tdata <= BinaryValue(binstr)

            if hasattr(self.bus, 'tkeep'):
                self.bus.tkeep <= BinaryValue(keepstr)

            if hasattr(self.bus, 'tstrb'):
                self.bus.tstrb <= BinaryValue(keepstr)

            yield RisingEdge(self.clock)

            if hasattr(self.bus, 'tready'):
                # other drivers wait for ReadOnly here; I don't understand why
                while not int(self.bus.tready):
                    yield RisingEdge(self.clock)

        self._idle_outputs()

    @coroutine
    def _send_stream(self, stream):
        for cycle in stream:
            if not self.on:
                self.bus.tvalid <= 0
                for _ in range(self.off):
                    yield RisingEdge(self.clock)
                self._next_valids()

            # Consume a valid cycle
            if self.on is not True and self.on:
                self.on -= 1

            self.bus <= cycle
            self.bus.tvalid <= 1

            yield RisingEdge(self.clock)

            if hasattr(self.bus, 'tready'):
                while self.bus.tready.integer != 1:
                    yield RisingEdge(self.clock)

        self._idle_outputs()

    @coroutine
    def _driver_send(self, transaction, sync=True, **kwargs):
        """Send a packet over the bus.
        Args:
            transaction (byte-like or iterable): Packet to drive onto the bus.
        If ``transaction`` is a string, we simply send it word by word
        If ``transaction`` is an iterable, it's assumed to yield objects with
        attributes matching the signal names.
        """

        if sync:
            yield RisingEdge(self.clock)

        if isinstance(transaction[0], int):
            yield self._send_bytes(transaction, **kwargs)
        elif hasattr(transaction, '__iter__'):
            yield self._send_stream(transaction, **kwargs)
        else:
            raise AttributeError("Transaction not uspported")


class AXIS_Monitor(BusMonitor):
    _signals = ["tvalid"]
    _optional_signals = ["tdata", "tkeep", "tready", "tlast", "tstrb", "tid",
                         "tdest", "tuser"]

    def __init__(self, entity, name, clock, lsb_first=True, tuser_bytewise=False, **kwargs):
        self._init_done = Event("Init Done") # workaround for scheduler immediately running newly added coroutines
        BusMonitor.__init__(self, entity, name, clock, **kwargs)

        if hasattr(self.bus, 'tdata'):
            self._n_bytes, rem = divmod(len(self.bus.tdata), 8)
            if rem:
                raise AttributeError("tdata width has to be multiple of 8")
        else:
            self._n_bytes = 1

        if hasattr(self.bus, 'tuser'):
            self._tuser_bytewise = tuser_bytewise
            if tuser_bytewise and self._n_bytes:
                self._user_bits, rem = divmod(len(self.bus.tuser), self._n_bytes)
                if rem:
                    raise AttributeError("in byte-wise mode tuser width has to be multiple of tdata width")
            else:
                self._user_bits = len(self.bus.tuser)

        self._lsb_first = lsb_first
        self._init_done.set()

    @coroutine
    def _monitor_recv(self):
        """Watch the pins and reconstruct transactions."""

        yield self._init_done.wait()

        # Avoid spurious object creation by recycling
        clkedge = RisingEdge(self.clock)
        rdonly = ReadOnly()

        class _dummy():
            def __init__(self, value):
                self.value = value

        tlast  = getattr(self.bus, 'tlast',  None)
        tready = getattr(self.bus, 'tready', _dummy(BinaryValue('1')))
        tkeep  = getattr(self.bus, 'tkeep',  _dummy(BinaryValue("1"*self._n_bytes)))
        tstrb  = getattr(self.bus, 'tstrb',  tkeep)
        tdata  = getattr(self.bus, 'tdata',  None)
        tid    = getattr(self.bus, 'tid'  ,  None)
        tdest  = getattr(self.bus, 'tdest',  None)
        tuser  = getattr(self.bus, 'tuser',  None)
        tvalid = self.bus.tvalid

        packet_buf = {}

        while True:

            yield clkedge
            yield rdonly

            if self.in_reset:
                if packet_buf:
                    self.log.warning("Discarding unfinished packet(s) as the bus is in reset")
                    packet_buf = {}
                continue

            if int(tvalid) and int(tready):
                if self._lsb_first:
                    byte_range = range(self._n_bytes-1, -1, -1)
                else:
                    byte_range = range(self._n_bytes)

                filtered_data = []
                filtered_user = []

                for b in byte_range:
                    byte_type = resolve(tkeep.value.binstr[b] + tstrb.value.binstr[b])
                    if byte_type == "11":
                        # data byte
                        if tdata:
                            filtered_data.append(int(resolve(tdata.value.binstr[b*8:(b+1)*8]),2))
                        if tuser and self._tuser_bytewise:
                            filtered_user.append(int(resolve(tuser.value.binstr[b*self._user_bits:(b+1)*self._user_bits]),2))
                    elif byte_type == "10":
                        # position byte
                        if tdata:
                            filtered_data.append(0)
                        if tuser and self._tuser_bytewise:
                            filtered_user.append(0)
                    elif byte_type == "01":
                        raise AXIS_ProtocolError("Invald combination of TKEEP and TSTRB byte qualifiers")
                    else:
                        # null byte
                        pass

                stream_id = (int(tid) if tid else None, int(tdest) if tdest else None)
                if not tlast or int(tlast):
                    recv_pkt = {}
                    try:
                        if tdata:
                            recv_pkt["data"] = b"".join(packet_buf[stream_id]["data"]) + bytes(filtered_data)
                        if tuser:
                            if self._tuser_bytewise:
                                recv_pkt["user"] = packet_buf[stream_id]["user"] + filtered_user
                            else:
                                recv_pkt["user"] = resolve(tuser.value.binstr)
                        if tid:
                            recv_pkt["tid"] = int(tid)
                        if tdest:
                            recv_pkt["tdest"] = int(tdest)

                        self._recv(recv_pkt)
                        del packet_buf[stream_id]
                    except KeyError:
                        # No buffered data
                        if tdata:
                            recv_pkt["data"] = bytes(filtered_data)
                        if tuser:
                            if self._tuser_bytewise:
                                recv_pkt["user"] = filtered_user
                            else:
                                recv_pkt["user"] = resolve(tuser.value.binstr)
                        if tid:
                            recv_pkt["tid"] = int(tid)
                        if tdest:
                            recv_pkt["tdest"] = int(tdest)
                else:
                    try:
                        if tdata:
                            packet_buf[stream_id]["data"].append(bytes(filtered_data))
                        if tuser and self._tuser_bytewise:
                            packet_buf[stream_id]["user"].extend(filtered_user)
                    except KeyError:
                        packet_buf[stream_id] = {}
                        if tdata:
                            packet_buf[stream_id]["data"] = [bytes(filtered_data)]
                        if tuser and self._tuser_bytewise:
                            packet_buf[stream_id]["user"] = filtered_user
