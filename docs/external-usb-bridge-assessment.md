# 外置 USB 桥接工程决策记录

日期：2026-11-16。范围：归档已有评估，不修改 RTL、不扩大实验；继续以 OTBN、OpenTitan 官方 P-256、OT HMAC 为密码架构偏好。

## 决策与容量预算

可编程 USB MCU 经 SPI 接入 GF180，是可行的原生 U2F HID 外桥路线，主要价值是降低 USB 模拟实现风险。普通串口桥与固定厂商 HID 桥不能因其 USB/HID 标签被当作 FIDO 外桥。外置 USB 本身不能使原密码架构进入 half/quarter。

当前本地 `librelane/slots/slot_1x0p5.yaml` 的 CORE_AREA 为 `[442,442,3490,2089]`，即 **3048×1647 µm = 5.020056 mm²**；quarter core 为 **1.732644 mm²**。旧上下文的 **5.461 mm² 已废弃，不再作为预算**。以上是 core 几何上限，尚未扣布线、供电、宏间距等。

8 KiB IMEM 用 10 个 1024×8 宏，候选 16 KiB 总宽 DMEM 用 39 个 512×8 宏。按实际 LEF 尺寸计算：

- 1024×8：301.300×515.810 µm，单宏 0.155413553 mm²；IMEM 合计 1.554135530 mm²。
- 512×8：301.300×321.890 µm，单宏 0.096985457 mm²；DMEM 合计 3.782432823 mm²。
- **SRAM 本体共 5.336568353 mm²，已超过 half 0.316512353 mm²（6.30%），占 half 的 106.30%。** 仅宏面积已排除该组织进入 half，quarter 更不可能。

`crypto-hw/evidence/results/imem8-summary.json` 的原 8 KiB IMEM / 32 KiB 总 DMEM 综合结果为：49 宏 7.615264097 mm²、154,030 个标准单元 4.268281024 mm²。以该逻辑面积作为筛选参考，候选 SRAM 加逻辑约 **9.604849377 mm²**，再加 OT HMAC **0.931858010 mm²**，约 **10.536707387 mm²**，尚未计 CPU 和平台服务。这里的 4.268281024 mm² 不是 DMEM 减半后的逻辑实测；独立 worker 的最新减半验证及资格限制以 `docs/opentitan-crypto-assessment.md` 为准，本记录不重复该工作。上述 SRAM 是 LEF footprint 计算，不是已完成布局或签核。

## 面积证据与收益边界

- **轻量协议引擎，标准单元映射实测**：`usb_fs_nb_pe` 为 1,348 cells，TT **0.039853856 mm²**、SS **0.042090765 mm²**，非缓冲、2 IN＋2 OUT endpoint、64 B 包。依据 `p0/RESULTS.md`。不含模拟 AFE，也不等于完整 SoC USB 实现。
- **完整 OpenTitan usbdev，标准单元映射实测**：**1.982875866 mm²**。其 512×32、2 KiB generic packet SRAM 被展开为 FF/mux；网表含 16,664 DFF、17,030 MUX2。不能将此结果称作纯协议逻辑、PHY 面积或已适配 SRAM 硬宏的 usbdev。依据 `docs/checkpoint1-soc-u2f-assessment.md` 及其综合证据。
- **模拟 AFE，GDS 包围框几何**：driver 1831.200×103.205 µm，差分 RX 457.180×56.310 µm，pullup 252.775×121.460 µm，两个单端 RX 各 469.840×57.710 µm，合计 **0.299663786 mm²**。不是综合面积或签核结果，不含 pad/ESD、隔离、布线。driver 长度大于 quarter core 的 1647 µm 长边；缺乏完整 LEF/Liberty 及物理签核。依据 `docs/gf180-usb-phy-assessment.md`。
- **packet SRAM 替代宏，仅容量/几何估算**：2 KiB 可用 4×512×8，约 **0.387941828 mm²**，或 2×1024×8，约 **0.310827106 mm²**；需另做接口/深度适配，不能直接视作已实现 usbdev。
- **未量化**：`soc/rtl/usb_u2f_bridge.sv` 的 EP0/HID 描述符及包寄存器，UART/SPI 控制、CDC、FIFO、流控、MMIO 和 pad 改动。现有资料不足以给出独立 GF180 串行桥面积。

相对轻 PE＋拟集成 AFE，已知可删除本体约 **0.339518–0.341755 mm²**，其中约 0.300 mm² 仅为模拟包围框。相对 FF 化完整 usbdev＋AFE，毛值约 **2.282540 mm²**。这两种基线互斥，不能累加；后者也不能代表优化后的片内 USB。净收益须计入被删除的端点控制并扣除串行桥、缓冲、CDC 和 pad 成本，目前不能给确定值。

## 外桥分类与候选

[FIDO 官方 U2F HID 规范](https://fidoalliance.org/specs/u2f-specs-master/fido-u2f-hid-protocol.html)要求 FIDO usage page **0xF1D0**、顶层 usage **0x01**，本项目目标为 **64 B IN/OUT report、双向 interrupt endpoint**。可改 VID/PID/字符串不等于可改 report descriptor。

1. **仅外置 PHY**：如 [TI TUSB1106](https://www.ti.com/product/TUSB1106)，只搬走 USB 电气收发，数字 PE/usbdev 及缓冲仍在本芯片；不是 UART/SPI 桥。
2. **普通 USB 串口桥**：CH340、CP2102N、FT232 的普通串口模式不能让浏览器直接识别 U2F HID。例见 [CP2102N 官方手册](https://www.silabs.com/documents/public/data-sheets/CP2102N-DataSheet.pdf)。自定义本机代理或非标准访问不等于浏览器原生 FIDO。
3. **固定功能 HID 桥**：[MCP2210 官方资料](https://www.microchip.com/en-us/product/MCP2210)的 64 B 厂商命令 reports、固定 vendor descriptor 与 NVRAM VID/PID/字符串设置，不提供所需的任意 FIDO descriptor 配置。[FT260 官方指南](https://ftdichip.com/wp-content/uploads/2024/12/AN_394_User_Guide_for_FT260.pdf)使用自己的 I²C/UART report ID/头部，也不能直接承载目标 FIDO reports。本次未核实到满足全部条件的固定功能 HID-SPI 桥。
4. **可编程 USB MCU**：固件控制完整描述符和端点，可实现 FIDO HID，再经 SPI/UART 转发。下面两款具备实现能力，但尚未完成本项目实机兼容性验证。

**原型优先 RP2040/Pico＋TinyUSB＋SPI。** [官方规格](https://www.raspberrypi.com/products/rp2040/specifications/)列出 USB 控制器/PHY、SPI/UART；[TinyUSB hid.h](https://github.com/hathach/tinyusb/blob/master/src/class/hid/hid.h)定义 FIDO usages，[hid_device.h](https://github.com/hathach/tinyusb/blob/master/src/class/hid/hid_device.h)提供 `TUD_HID_REPORT_DESC_FIDO_U2F(64)`，[双向 HID 示例](https://github.com/hathach/tinyusb/blob/master/examples/device/hid_generic_inout/src/usb_descriptors.c)提供 IN/OUT 端点配置。需组合成实际桥固件，不能将通用示例原样称为 FIDO。RP2040 的外部启动 flash 计入板级 BOM。

**产品化候选 STM32F042K6＋Custom HID＋SPI。** [ST 官方手册](https://www.st.com/resource/en/datasheet/stm32f042k6.pdf)确认 USB FS、SPI/UART、片内 flash；[ST 官方 Custom HID 类源码](https://github.com/STMicroelectronics/stm32-mw-usb-device/tree/master/Class/CustomHID)提供 report descriptor 与 IN/OUT 端点配置。本方案须将 usage page/usage 设为 FIDO、64 B reports，并配置 64 B IN/OUT interrupt endpoints；vendor HID 默认描述符不是 FIDO。能力明确，但仍需固件与主机实测。

## 接口、安全与下一步

SPI 通常需 CS/SCK/MOSI/MISO 四线，可加 ready/IRQ；UART 至少 TX/RX，可加 RTS/CTS。`docs/phy-io-plan.md` 已预留 SPI 四线和外置 PHY 多根信号，因此不能机械声称新增四个物理 pad，或释放 USB pad 就能缩小固定 die/pad 环。另需核对 3.3 V 电平、供电、复位、断电反灌与时钟；移除 USB 48 MHz 需求不等于本芯片不需时钟。

纯线速估算，64 B UART 8N1 在 115200 baud 为 **5.56 ms**、1 Mbaud 为 **0.64 ms**；SPI 在 1 MHz 为 **0.512 ms**、4 MHz 为 **0.128 ms**。均不含帧头、USB 调度及排队。1 KiB 在 115200 baud 已需 **88.9 ms**，优先采用带背压、超时及复位重同步的 SPI mailbox。

外桥视作可窥探、篡改、重放和拒绝服务的不可信传输。私钥、派生、P-256、HMAC、U2F 注册/认证语义与计数器留在 GF180；不开放任意 MMIO/DMA、裸 OTBN 调用或读密钥。本芯片校验长度、请求与状态；实体按键直接接本芯片，授权绑定当前请求并一次消费，不能信任桥上报“已触摸”。CRC 只能检测链路错误，不能认证恶意桥。当前 `soc/rtl/soc_usb_top.sv` 的 `button_i` 仍绑零，尚不是已实现的用户在场门控。

最小后续验证建议（本次未执行）：先用 Pico 核验实际枚举的 FIDO usages、64 B 双向端点与 INIT/PING/多包/复位；再验证 SPI 流控、目标 OS/浏览器 WebAuthn 注册认证和本芯片按键门控；最后单独综合串行控制与缓冲以获得净面积。描述符正确只是兼容性的必要条件。无需为此外桥试验重复正在进行的密码架构实验。
