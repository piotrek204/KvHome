# KvHome - A simple multi-platform application for visualization and control of the heating process at home.

The goal of the project is found an easy way to create an application with a simple user interface,
available for different operating systems and integrating various physical devices (IoT).

Environment:
<pre>
  ---------              ----------------                  --------------
  |       |    RS-485    | Converter    |      eth         |            |
  |  PLC  | ------------ | RS-485 / Eth | ---------------- | KvHome App |
  |       |  Modbus RTU  | TCP Server   |  Modbus RTU  |   |            |
  ---------              ----------------  over TCP    |   --------------
                                                      ...
                                             (max 4    |   --------------
                                              clients) |   |            |
                                                       --- | KvHome App |
                                                           |            |
                                                           --------------
</pre>

## Screen shots (Ubuntu):
### Live Data tab:
<img src="/screenshot/Live_data.png" width="440px">

### Chart tab:
<img src="/screenshot/Chart.png" width="440px">

### Heater details tab:
<img src="/screenshot/Heater_details.png" width="440px">

### Heater details tab - setting value in PLC:
<img src="/screenshot/Set_value.png" width="440px">
