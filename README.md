# cocotbext-axis
An extension for [cocotb](https://github.com/cocotb/cocotb) providing communication via the AMBA 4 AXI4-Stream Protocol.
At the moment this is mostly untested and work in progress.

## AXIS_Driver
Driver class representing a Stream Master.

The class inherits from `cocotb.drivers.ValidatedBusDriver` to allow generating transactions with gaps in `TVALID`. The standard only requires `TVALID` to be present on the bus, all other signals are optional.

### Constructor arguments

 - **entity**: A handle to the simulator entity.
 - **name**: Name of the bus. This is used to bind the signals belonging to the bus. For example if your bus has signal names like `m_axis_tvalid` and `m_axis_tready`, set this to `"m_axis"`.
 - **clock**: A handle to the clock associated with the bus.
 - **lsb_first**: Optional reversing of byte order on the bus. Defaults to `True`, i.e. the first byte of a stream is `tdata[7..0]`

## AXIS_Monitor
The monitor class only translates transactions on a stream and sends them to a testbench. If an AXI Stream Slave is to be simulated, the signal `TREADY` has to be driven externally, e.g. using a `cocotb.drivers.BitDriver`

### Constructor arguments
 - **entity**: A handle to the simulator entity.
 - **name**: Name of the bus. This is used to bind the signals belonging to the bus. For example if your bus has signal names like `m_axis_tvalid` and `m_axis_tready`, set this to `"m_axis"`.
 - **clock**: A handle to the clock associated with the bus.
 - **lsb_first**: Optional reversing of byte order on the bus. Defaults to `True`, i.e. the first byte of a stream is `tdata[7..0]`
 - **tuser_bytewise**: Optional setting associating the data on the `TUSER` stream to bytes in the `TDATA` stream.