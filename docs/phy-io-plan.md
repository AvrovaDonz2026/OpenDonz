# USB PHY / I/O 边界：第一步工程方案

日期：2026-11-16。基线：`ef14285cf5b0709539449f1bea7fca364bdb7d21`。
状态：可审阅的接口与 pad 预留方案；未实现 PHY，未冻结封装 pin number。
本阶段不改 P0 RTL、SDC、依赖锁、验证脚本、RESULTS，也不接入模板计数器顶层。

## 1. 调查范围与证据等级

已检查根 README、Makefile、flake.nix/flake.lock、docs/plan.md、p0/README.md、
p0/RESULTS.md、p0/src 全部文件（仅 usb_fs_nb_pe_top.sv）、依赖锁、
src/chip_top.sv、chip_core.sv、slot_defines.svh、quarter slot YAML、主配置、
pad-ring 脚本及 PDN/SDC 接口。仓库结构包括模板 src/cocotb、librelane 的
slot/macros/PDN 配置、wafer.space 标识宏 ip、独立 p0 数字验证和 docs 规划。
`ip/` 现有宏是标识/logo，不是 USB 模拟 IP。

本地已获取的有效资源是 P0 的两份 combined Liberty：
`gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.combined.lib` 和
`gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.combined.lib`。
其来源 commit 为 `43beb45e4d323a76239de436db2df6732e9a689b`，摘要见
[p0/dependencies.lock](../p0/dependencies.lock)。它们是标准单元库，不提供 pad/PHY。
本次未发现项目 `gf180mcu/` 下完整已安装 PDK 或可用 I/O LEF/GDS/Liberty/SPICE。
Makefile 的 `PDK_COMMIT=792ef67037d74c8c51811eab3ce23cf793491296`
只是拟获取版本；不能把配置值当作已安装/已验证证据。

通过官方在线文档确认下述 fd_io 单元与功能（2026-11-16 读取，`latest` 是可变文档，
尚非锁定制造输入）。尝试通过 gh 获取 fd_io/OCD 源码均返回 GraphQL Forbidden；
没有取得其 commit 或实体 views，因此不声称已完成 I/O 源码/版图检查。
OCD 名称只由本仓模板证实为引用，不等于本地可用 cell。

## 2. 真实 I/O cell 与电压/ESD 证据

官方 [cell list][cells] 明列以下完整名称：

- `gf180mcu_fd_io__bi_t`：4/8/12/16 mA 可选驱动、三态输出、fast/slow slew、
  CMOS/Schmitt 接收及弱上拉/下拉。PDRV1/PDRV0 依次为 00/01/10/11。
- `gf180mcu_fd_io__bi_24t`：24 mA 双向三态 pad；本模板所有 bidir 均引用它。
  不应向该 cell 虚构 PDRV 接口；修改为 bi_t 前须核实实际 Verilog/LEF/pin。
- `gf180mcu_fd_io__in_c`、`gf180mcu_fd_io__in_s`：CMOS / Schmitt 输入 pad，PU/PD 可控。
- `gf180mcu_fd_io__asig_5p0`：带双二极管保护的模拟 pad，列出的 DC 能力 10 mA。
  它没有差分接收器、比较器或 USB TX。
- `gf180mcu_fd_io__dvdd`、`gf180mcu_fd_io__dvss`：电源/地 pad，文档列 DC 能力各 60 mA；
  不据此计算整芯片可用电流，仍需 bonding、PDN、IR/EM 与 ESD 约束。
- `gf180mcu_fd_io__cor`；`gf180mcu_fd_io__fillnc`、`fill1`、`fill5`、`fill10`；
  `gf180mcu_fd_io__brk2`、`brk5`（以上简写 suffix 均带 `gf180mcu_fd_io__` 前缀）。
  filler/corner/breaker 由真实 padring flow 配置与版图规则决定，不可任意删改。
  文档要求 fillnc 不可单独用，须配合 filln (n>=2)。

本仓 fd_io 分支把 VDD/VSS pad 实例也映射成 dvdd/dvss，并在显式 power-pin 模式
短接 VDD=DVDD、VSS=DVSS；未见独立的 fd_io__vdd/vss cell 证据。
OCD 分支引用 `gf180mcu_ocd_io__vdd`、`vss`、`dvdd`、`dvss`、`in_s`、`in_c`、
`bi_24t`、`asig_5p0`（同一前缀），但尚未取得实体模型验证独立电源域和电压关系。
README 中 OCD 的 DVDD>=VDD 及硅验证状态属于模板声明，本阶段不作为签核。

电压证据必须分开看：库称为 5V wide-range；[conditions][conditions] 页列 4.5/5/5.5 V；
[corners][corners] 页同时明确列 3.3 V TT、2.97 V SS、3.63 V FF，以及 5 V 和 2.5 V 组。
因此可确认存在 3.3 V 表征条目，但仍须取得所选安装版本的实际 3.3 V views、
工作条件与输入阈值说明。P0 core 的 SS 3.00 V 不等于 pad 的 SS 2.97 V。
初步设计目标是 core 与 I/O 统一 3.3 V，由外部稳压供电；USB VBUS 5 V
不接到 VDD/DVDD，也不未经审查直接接数字 pad。

[数字控制真值表][digital]：OE=1 使能输出；IE=1 使能输入；IE=OE=1 为禁用组合。
空闲/接收用 OE=0, IE=1；发送用 OE=1, IE=0；禁用用 OE=IE=0。
PU=PD=0 关闭弱拉，CS=0 CMOS/1 Schmitt，SL=0 fast/1 slow。
这些是 GPIO 功能，驱动电流与最高频率不证明 USB 阻抗、交叉点、接收灵敏度或眼图合规。

[power][power] 页说明每个 dvdd/dvss 内含一个 ESD circuit、每个 cor 内含两个。
[ESD 页][esd] 列目标 HBM 2000 V / MM 200 V / CDM 500 V；这是文档目标，
不是本芯片测试结果，也不是 USB 连接器 IEC 系统级 ESD 认证。
[模拟 pad 页][analog] 明确只有 HBM 二极管；接内部电路必须在受保护器件附近增加
secondary/CDM 网络（该页建议 diode perimeter >25 µm、poly resistor >50 Ω）。
未核实独立、可直接实例化的 USB ESD/rail clamp 宏，不能编造其名称。

## 3. 当前 PE 的数字接口契约

以 [usb_fs_nb_pe_top.sv](../p0/src/usb_fs_nb_pe_top.sv) 为唯一 P0 RTL 边界：

- `clk_i`：48 MHz 单时钟，20.833333 ns；不含 PLL/振荡器。
- `rst_ni`：低有效异步置位复位，两级上升沿释放。已接受的映射复位修复只在
  现有释放相对时钟沿后 0.5–3 ns 的契约及 TT/SS 下闭合；普通板级 reset pad
  无法自动保证这一相位。符合释放契约后至少等到第三个上升沿再启动流量/写入。
  任意相位 reset、POR、最短脉宽、fast corner、pad 延迟及 CTS/RDC 仍未解决。
- `link_reset_i` 高有效且同步于 48 MHz，`link_active_i` 为链路允许响应状态；
  `dev_addr_i[6:0]` 为设备地址。PE 不自带完整 USB 总线 reset/suspend/attach 控制器。
  不能将外部 rst_n 与 USB bus reset 混为一个信号。
- `cfg_eop_single_bit_i`、`cfg_use_diff_rcvr_i`、`cfg_pinflip_i`、
  `tx_osc_test_mode_i` 为配置；产品默认禁用 oscillator test，pinflip=0，
  EOP 策略需单独冻结。差分接收配置不是片内差分接收器的实例。
- `usb_d_i` 是外部差分接收器的数字判决；`usb_dp_i`/`usb_dn_i` 是两条线各自的
  数字电平。在 differential 模式也必须接入 DP/DM 单端观察以识别 SE0。
  `diff_rx_ok_i` 表示接收器有效，上电稳定前为 0；无外置 differential receiver 时
  不能把 DP XOR DM 当作 usb_d_i 来冒充差分判决。
- `usb_dp_o`/`usb_dn_o` 为逐线数字 TX，`usb_d_o`/`usb_se0_o` 为 D/SE0 TX 编码，
  `usb_oe_o` 高有效发送使能。只有适配实际收发器或 pad 后才可能驱动线。
  P0 自身没有 `usb_dp_pullup_o`、VBUS detector、attach 或模拟 pull-up 电路。
- RX 三输入在现有 STA 中是异步/unconstrained；上游源码注释的 synchronous
  不改变当前实际 STA 边界。接 pad 后需评估采样延迟、亚稳态、两路 skew、输入阈值，
  不能直接沿用原 STA 的 I/O load/arrival 当整片结论。

端点均属于片内 48 MHz 域，不应逐位引出为封装端口：

- 2 个 IN + 2 个 OUT，最大包长 64 B；endpoint selector 为 4 bit，byte address 为 6 bit。
- OUT：`out_ep_current_o`、`out_ep_newpkt_o`、`out_ep_data_put_o`、
  `out_ep_put_addr_o[5:0]`、`out_ep_data_o[7:0]`；`out_ep_acked_o` 提交、
  `out_ep_rollback_o` 丢弃；`out_ep_setup_o[1:0]` 指示 SETUP。
  输入 enabled/control/full/stall/iso 各 2 bit。
- OUT data strobe 包含最后两个 CRC16 字节，含 ZLP；地址到 63 饱和，NAK 时会停止推进。
  必须用带 CRC 尾部剥离的 staging/rollback 协议，收到 acked 后提交。
  不可直接按 put_addr 写 64 B RAM。该行为已有 P0 定向测试证据。
- IN：`in_xact_starting_o` / `in_xact_start_ep_o` 供事务快照；current/get_addr/data_get/newpkt
  请求数据，`in_ep_data_i[7:0]` 回数据，enabled/stall/has_data/data_done/iso 各 2 bit。
  `in_ep_xact_end_o` 与 rollback 管理提交/重读；保持事务数据以支持未收到 ACK 时重传。
- toggle 读写为 IN/OUT 各 2 bit status/mask，加各自 we；SOF detected/valid、
  frame_index[10:0]、RX idle/J、CRC5/CRC16/PID/bitstuff errors 与 4 个 event 输出
  留在片内状态/诊断接口。EP0/descriptor/HID、包缓存与 CSR/SPI 桥尚未实现。

## 4. Wrapper 分层决策

本轮交付文档与机器可检查的候选 pin 预留，不新增可被误认为已可工作的 chip RTL。
理由：完整 I/O views、收发器型号/极性/模式、POR/reset 和端点控制均未冻结。

后续独立实验 top 的层次为：保留模板 `chip_top` 的 pad 实例/供电/ID 位置，
新增独立 core adapter，adapter 内连接未改动的 P0 top、端点控制与 link manager；
外侧使用经验证的 GF180 GPIO cells 接外置 USB FS 收发器数字端。
连接器 D+/D−、1.5 kΩ FS pull-up/开关、串阻、VBUS 检测和连接器 ESD 在板级 PHY 边界。
外置器件须能提供 differential RX 判决以及 DP/DM 单端观察，TX 支持 D/SE0
或逐线模式。只有 ULPI/UTMI 接口的器件不能直接接当前 PE，须增加协议适配。
尚未选择可采购型号，外置路线也不是已完成的硬件方案。

另一实验路线为片内 GPIO pad 直驱：DP/DM 接 bi_24t 的 A/Y，OE=usb_oe_o、
IE=~OE，PU=PD=0，cfg_use_diff_rcvr_i=0；未用 usb_d_i 可固定为已定义电平。
实际 OE/IE 路径需验证不存在瞬时禁用组合、输出争用或不安全 turn-around。
CS/SL 必须由 SPICE 与接收阈值/眼图评审决定，不能预先宣布 fast 或 slow 合规。
该路线需在 3.3 V PVT、封装/PCB/串阻/负载下证明 TX impedance、slew、crossing、
SE0、RX threshold、leakage、attach/detach 与断电反灌。否则不进入制造基线。
普通 pad 不是 USB PHY；模板文档中的直连设想不足以解除这些依赖。

## 5. Quarter slot 候选 pinout（未冻结）

结构化候选位于 [phy-io-pinout.json](phy-io-pinout.json)。以现有 0p5x0p5 pad index
和 YAML 顺序为坐标，保留所有 pad 数、四边顺序及电源/地；这些不是封装 pin number。
本地 48 个 signal pad = clk/reset 2 + input 4 + bidir 38 + analog 4；另有电源/地 8。
外置 PHY 是本轮优先评估模式，direct-pad 是互斥的另一种 build/板卡方案，
不做能在未审查情况下热切换的模拟 mux。

clk_PAD/rst_n_PAD 保持现位置。South bidir[0:6] 预留给外置 PHY 的 TX D、SE0、OE、
attach request，以及 RX differential/DP/DM 数字信号；East bidir[7] 接 receiver-ready。
input[0] 是经过板级 3.3 V 调理的 vbus_present，input[1] 为 presence 按键，
input[2:3] 为候选配置 strap；East bidir[8:11] 预留 SPI CSn/SCK/MOSI/MISO，
bidir[12] 预留状态 LED。其余信号 pad 保持未分配，analog[0:3] 不接未审查电路。

direct-pad 实验中仅重解释 South bidir[0:1] 为 USB DP/DM、bidir[3] 为外部 pull-up
switch 的逻辑控制。相邻 pad 是否满足连接器/COB 走线和 ESD 要求仍需核实。
外置 PHY 模式不能同时把同一 pad 连接到 USB 线。JSON 标注的是期望功能与方向，
不是对现有 counter core 的改线，也没有赋予任何 pad 5 V VBUS 输入许可。

attach request 上电/复位默认 0（外部下拉保证 core 尚未供电时也关闭），TX OE 默认 0，
非 TX pad 默认 OE=0，弱拉关闭，strap/input pad 按需使能接收；外部 PHY ready=0
时保持 diff_rx_ok=0、link_active=0。attach=1 还须 VBUS 有效、时钟/复位稳定、
端点与描述符已就绪，并经 link manager 管理。此策略尚待 RTL/板级联合实现。
SPI 是端点控制候选，不承诺当前 PE 可直接由 SPI 驱动；需 CDC、事务缓冲与流控。

## 6. 待办与下一步门槛

1. 获取并锁定完整 gf180mcuD 安装、fd_io 源码版本及 license；记录各 cell 的
   Verilog、LEF、GDS、Liberty、SPICE 路径与 SHA256，核实 3.3 V 角、power pin、
   corner/filler/ESD continuity 与所选 flow 的映射。OCD 替换需单独取证。
2. 选择可采购外置 FS transceiver，核对 TX 编码、OE 极性、RX D/DP/DM、ready、
   supply/logic levels、上电/断电行为和 pull-up 控制。若接口不匹配，先明确 adapter 成本。
3. 取得当期 wafer.space slot、bond map、COB/breakout 规则；用 JSON 候选逐项核对。
   不减少电源/地或改变 pad 位置，不把当前 YAML 当作运营方批准。
4. 单独解决 reset 任意相位释放/外部同步复位的契约；将 pad/时钟/POR delay 纳入
   新 top 的 STA/RDC，保留 P0 既有验证作为独立结果。模板配置当前 25 MHz/40 ns，
   不可直接用于 PE 48 MHz。flake 只提供工具，不安装 USB PHY 或保证完整 PDK。
5. 上述依赖明确后再添加隔离 wrapper 与 pad adapter；先验证 default/断电/转向控制，
   然后加入 EP0/link manager、包提交/CRC tail 处理、枚举与 SPI/端点回归。
6. direct-pad 如继续：先形成含真实模型的 SPICE deck、PVT/封装/板级负载和 USB FS
   评审项目，再决定串阻与 SL/CS。外部 1.5 kΩ pull-up 不可由内部弱拉替代。

本阶段检查：`python3 scripts/check-phy-io-plan.py` 核对 pin 资源/冲突/PE 端口与
本地库 hash；`shasum -a 256 -c p0/evidence/sources.sha256` 保全既有 P0；
`git diff --check` 检查补丁格式。未重跑数字 PPA，不将文档更新算作新 STA/PHY 验证。

[cells]: https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html
[digital]: https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/digital.html
[conditions]: https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/conditions.html
[corners]: https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/corners.html
[power]: https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/power.html
[esd]: https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/esd.html
[analog]: https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/analog.html
