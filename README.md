# KvHome - A simple multi-platform application for visualization and control of the heating process at home.

The goal of the project is found an easy way to create an application with a simple user interface,
available for different operating systems and integrating various physical devices (IoT).

KvHome has been created in Python 2.7.14 using Kivy framework. Tested on Ubuntu and Android.

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

## Screen shots Ubuntu/Android:
### Live Data tab:
<img src="/screenshot/Live_data_ubuntu.png" width="440px"><img src="/screenshot/Live_data_ubuntu_android.png" width="440px">

### Chart tab:
<img src="/screenshot/Chart_ubuntu.png" width="440px"><img src="/screenshot/Chart_android.png" width="440px">

### Heater details tab:
<img src="/screenshot/Heater_details_ubuntu.png" width="440px"><img src="/screenshot/Heater_details_android.png" width="440px">

### Heater details tab - setting value in PLC:
<img src="/screenshot/Set_value_ubuntu.png" width="440px"><img src="/screenshot/Set_value_android.png" width="440px">

