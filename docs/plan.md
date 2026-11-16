# OpenDonz 计划：OpenTitan 精华移植到 GF180MCU，做 CanoKey 类安全钥匙

状态：草案 v0.5（2026-11-15）。本版按“移植适合 CanoKey 的部分”重排目标、IP 依赖与验证门槛；保留既有面积分析作为历史筛选估算，不把估算视为签核数据。
第 2 节和第 11 节的逻辑/宏面积仍是早期估算；所有流片结论须由 P0/P1 的真实综合、宏 LEF、floorplan、STA、PDN、DRC/LVS 与电气验证替换。本计划不把几何推算当作可制造性或封装兼容性结论。

## 0. 结论

1. 项目目标是**选择性移植 OpenTitan 的可复用硬件与安全设计模式**，实现 CanoKey 类设备；不移植完整 OpenTitan top/chip，也不以“OpenTitan 级安全”作未经验证的承诺。功能按阶段递进：USB FS + CTAP1/U2F 验证 → FIDO2/CTAP2 核心功能 → 可选 OpenPGP/PIV/OATH。
2. wafer.space 版图基线优先采用 **0.5×0.5 slot 的默认 pad/COB 组合**；若接口/功能或实测 PPA 不够，再评估 **1×0.5 slot** 作为次选。两种都以当期官方 slot/pad/封装文件和完整物理验证为准；此前“改 pad 环/自绑线可扩大 core”的数字不是基准承诺。
3. 采用 P0 验证片/原型先回答 USB PHY、存储、熵源、工具链与真实面积问题，再决定产品芯片。完整 CanoKey 是否可运行、需要多少 RAM、任何面积/安全结论均不预先承诺。
4. **流片日程与价格须重新确认。** 本文原 Run 3 日期是 2026-11-06 草案记录，不能作为当前采购依据；P0a 必须核对官方最新 run 页面。
5. **全专用化（第 11 节）**：去掉 CPU 和固件、所有功能都做成专用硬件，只作为 CTAP1/U2F 的候选路线；其面积和可制造性仍需 P0/P1 验证。OpenPGP、PIV、OATH、passkey 不适合直接专用化。

## 1. 已核实的数据与配置事实

| 项目 | 数值 | 来源 |
|---|---|---|
| 0.5×0.5 slot die / 当前 core | YAML DIE_AREA 为 1936×2531 µm（4.900 mm²）；CORE_AREA 为 [442,442,1494,2089]，面积 1.732644 mm²。当前 pad list 有 48 个信号 pad（输入/双向/模拟）及供电 pad | 本地 `librelane/slots/slot_0p5x0p5.yaml`；slot/供货规格仍须以 wafer.space 当前 run 文件为准 |
| 0.5×1、1×0.5 core | 4.46 mm²、5.02 mm²（此顺序依本地 slot YAML；本计划备选 1×0.5） | 同上 |
| 1×1 die / core | 3.93×5.12 mm / 12.92 mm² | 同上 |
| Run 3 价格（1,000 die） | 0.5×0.5 $3,000；0.5×1、1×0.5 $5,000；1×1 $8,000（早鸟已结束） | wafer.space 官网 |
| Run 3 时间 | 购买截止 12-09，GDS 截止 12-16，2027 Q2 发货 | wafer.space 官网 |
| 工艺 | gf180mcuD，5 层金属，有 MIM 电容 | wafer.space 官网；`Makefile` |
| 标准单元 7t | NAND2_1 = 2.80×3.92 µm = 11.0 µm²（1 GE）；DFFQ_1 = 63.7 µm²（5.8 GE） | gf180mcu_fd_sc_mcu7t5v0 LEF |
| 逻辑密度（推算） | 50% 利用率时约 0.022 mm²/kGE；quarter core 只放逻辑约 79 kGE | 由上一行推算 |
| OCD SRAM（3.3V） | 64×8：0.046 mm²；256×8：0.068；512×8：0.097；1024×8：0.155 mm²/KB | gf180mcu_ocd_ip_sram LEF |
| Foundry SRAM | 512×8：0.209 mm²（0.419 mm²/KB），比 OCD 1024×8 大 2.7 倍 | gf180mcu_fd_ip_sram LEF |
| eFuse | 开源编译器，阵列密度最高约 10 kbit/mm²；首颗测试片在 Run 1，原定 2026 夏季出结果 | egorxe/gf180_efuse_compiler |
| canokey-stm32 资源 | 代码 190 KB + littlefs 66 KB flash，64 KB RAM（heap 16 KB、stack 8 KB） | canokey-stm32 链接脚本 |
| Ibex 面积（Yosys） | micro 16.9 kGE；small 26.6；maxperf 32.5；maxperf-pmp-bmfull 66.0 | lowRISC/ibex README |
| OpenTitan AES | 不加掩码只做 AES-128：12~22 kGE；加掩码的整个 IP：136 kGE（去掉 GCM 112） | `hw/ip/aes/doc/theory_of_operation.md:176` |
| OpenTitan KMAC | 约 200 kGE | `hw/ip/ascon/doc/theory_of_operation.md:206` |
| OTBN 存储 | IMEM 4 KB；DMEM 4 KB，字宽 312 bit（256 + ECC） | `hw/ip/otbn/rtl/otbn_core.sv`、`otbn_pkg.sv` |
| usbdev | 12 个端点，2 KB 包缓冲（512×32，单口，无 ECC），整个 IP 跑在 48 MHz | `hw/ip/usbdev/rtl/usbdev.sv`；`xbar_main.hjson` |

**封装选择：** 当前默认优先 0.5×0.5 的官方默认 pad/COB；1×0.5 是备选 slot，不等于改变 pad 环或可沿用同一 COB。需 P0a 获取 wafer.space 当期 slot YAML、pad 坐标、COB/breakout 约束，逐项确认 pad 数、供电、USB 差分引脚和测试接口。面积表中的 slot core 是模板几何，不代表可用逻辑面积。

以下两条是配置/宏选择约束，不应误读为已验证的芯片电气结论：
- 用 foundry SRAM 做 32 KB 要 13.4 mm²，比 1×1 的整个 core 还大。**TO-B 只能用 OCD SRAM。**
- OCD SRAM 只有 3.3V 版本；USB D+/D- 也不能超过 3.6V。**全片统一 3.3V**（core、IO、SRAM）。

模板当前实现的是示例计数器，不是 OpenTitan：`src/chip_core.sv` 实例化两颗 512×8 SRAM；`Makefile` 默认 `SLOT=1x1`、foundry 5V SRAM、7t5v0 与 fd_io。0p5x0p5 只是可选 slot。3.3V OCD 配置需显式选 `PAD=gf180mcu_ocd_io SRAM=gf180mcu_ocd_ip_sram`，其余电压/宏适配及完整 signoff 仍需实测。

## 2. 面积预算（估算，±30~50%）

换算：50% 利用率下 1 kGE ≈ 0.022 mm²；SRAM 宏另加约 10% 的 halo。

### 2.1 为什么 quarter slot 放不下带 CPU 的单芯片

| 模块 | kGE |
|---|---|
| Ibex micro（RV32EC） | 17~20 |
| TL-UL 总线和适配器 | 4~8 |
| usbdev 逻辑 | 15~25 |
| QSPI XIP 控制器 | 4~8 |
| 启动 ROM（标准单元综合，约 4 KB） | 5~15 |
| 环振 TRNG、eFuse 接口、GPIO、定时器、UART | 7~12 |
| **逻辑合计** | **52~88 kGE ≈ 1.1~1.9 mm²** |
| usbdev 包缓冲缩到 1 KB（4×256×8）+ 1 KB 数据 RAM（4×256×8） | ≈ 0.6 mm² |
| **合计** | **1.7~2.5 mm²，是 core 的 100%~150%** |

这还没算调试模块、PLIC、HMAC、AES，而且 1 KB RAM 跑不了 canokey-core。
usbdev 包缓冲缩到 1 KB 要改 `SramDepth`，源码注释说寄存器定义也得跟着改。

### 2.2 TO-A（0.5×0.5，无 CPU）

| 模块 | kGE |
|---|---|
| SPI 转 TL-UL 桥（新写，外部 MCU 当总线主机） | 2~4 |
| TL-UL 总线 | 3~6 |
| usbdev 逻辑 | 15~25 |
| 环振 TRNG + 健康测试 | 3~6 |
| eFuse 接口 + 简易生命周期原型 | 2~4 |
| GPIO、时钟复位、测试 mux | 2~3 |
| **逻辑合计** | **27~48 kGE ≈ 0.6~1.1 mm²** |
| usbdev 2 KB 包缓冲（4×512×8，不改 RTL） | ≈ 0.43 mm² |
| eFuse 阵列（256~512 bit） | ≈ 0.05~0.1 mm² |
| **合计** | **1.1~1.6 mm²，是 core 的 62%~91%** |

- SRAM PUF 不需要额外的宏：usbdev 包缓冲没有 ECC，可以在上电后、写入前经 TL-UL 直接读出原始内容。
- 不放 CPU 的理由：Ibex 已经在别的工艺上流片过多次，它在 GF180 上的风险主要是时序，用 STA 就能评估。
  把面积留给 USB 和存储实验更值。P0 实测如果面积有富余，再考虑加 Ibex micro。
- SPI 桥的替代方案是复用 rv_dm 的系统总线访问（JTAG 当主机），省掉新写的模块，但面积更大、速度更慢。
- eFuse 烧写需要的电源和引脚以编译器文档为准；quarter slot 有 4 个 analog pad 可用。

### 2.3 TO-B（1×1）

| 模块 | kGE |
|---|---|
| SecureIbex（锁步、寄存器堆 ECC、PMP、Zb*） | 80~130 |
| usbdev 逻辑 | 15~25 |
| TL-UL 总线（带端到端完整性） | 10~20 |
| HMAC（SHA-2） | 25~45 |
| AES（不加掩码） | 15~40 |
| keymgr-lite + eFuse/生命周期 lite | 15~30 |
| SRAM 加扰 + XIP 在线解密（PRINCE） | 15~30 |
| 启动 ROM（8~16 KB，标准单元综合） | 15~40 |
| TRNG、rv_dm、UART、GPIO、定时器、PLIC、alert-lite、QSPI | 40~65 |
| **逻辑合计** | **230~425 kGE ≈ 5.1~9.4 mm²** |
| 主 SRAM 24~32 KB，带 SECDED（每 4 KB 用 5 片 1024×8：4 条数据道 + 1 条 ECC 道） | ≈ 5.1~6.8 mm² |
| usbdev 2 KB 包缓冲 | ≈ 0.43 mm² |
| **合计** | **10.6~16.6 mm²，是 core 的 82%~128%，中值约 105%** |

中值略超。超了按这个顺序砍：
1. 去掉锁步：约 −1 mm²。
2. RAM 定在 24 KB。
3. AES 改软件：约 −0.3~0.9 mm²。

做完 1 和 2，中值约 11.7 mm²（91%）；再做 3，约 11.1 mm²（86%）。

**OTBN 为什么放不下：**
- 逻辑 150~250 kGE（我的估算），约 3.3~5.5 mm²。
- IMEM 4 KB × 39 bit：5 片 1024×8，约 0.78 mm²。
- DMEM 只有 128 行，但字宽 312 bit，要 39 片宏并排；用 256×8 也浪费一半容量，约 2.6 mm²。
- 合计约 7~9 mm²，占 1×1 core 的一半以上。

## 2.4 CanoKey 功能目标与产品边界

| 阶段 | 功能目标 | 实现含义 / 暂不承诺 | 出口条件 |
|---|---|---|---|
| P0：可行性验证 | host 可枚举 USB FS；验证 U2F/CTAP1 所需 HID 传输路径；板级 MCU/FPGA 可驱动原型 | 不构成安全钥匙，不含可信根/量产生命周期；USB PHY、电气和熵均为待测 | P0 go/no-go 全部量化通过 |
| P1：最小安全钥匙原型 | CTAP1/U2F 注册/认证，设备密钥保护、用户在场；功能可在 FPGA/仿真验证 | 是否专用状态机或小 CPU 由需求与 PPA 决定；固定 ROM attestation 私钥不可提供可信认证 | 向量、浏览器互操作、密钥不泄漏性质通过 |
| P2：CanoKey 主功能候选 | 先实现 CTAP2 的具体子集（HID、CBOR、PIN/UV、resident/passkey 需求逐项定）；再评估 OpenPGP、PIV、OATH | 这是固件/存储密集路线；不能从 U2F 原型推断可装进 0.5×0.5；RAM 峰值必须对真实 canokey-core 构建测量 | 功能矩阵冻结、峰值 RAM/ROM/flash 及性能实测、目标 slot 完整 PPA 通过 |
| P3：产品化安全边界 | 安全启动、密钥隔离、更新、防回滚、生命周期、恢复/备份 | 需明确威胁模型、制造注钥和故障/侧信道评估；不宣称认证级安全 | 安全评审与硅后测试按产品风险另定 |

**512 B SRAM 的边界：** 它仅是第 11 节专用 CTAP1/U2F 微架构的候选工作区，需由活跃区间分析、形式/断言检查和 RTL 峰值仿真确认；它不代表 512 B 可运行完整 CanoKey 固件，更不支持据此推断 CTAP2、OpenPGP/PIV/OATH 可行。

## 3. OpenTitan 模块取舍

| 模块 | 决定 | 理由 |
|---|---|---|
| Ibex（rv_core_ibex） | 候选，P0 对照 | 若走固件路线再评估 SecureIbex/PMP；面积紧时先关锁步 |
| TL-UL、tlgen、reggen | 保留 | 总线完整性、CSR 生成、DIF 直接复用 |
| prim 库 | 保留，新增 `prim_gf180` | 稀疏 FSM、加固计数器、SECDED、mubi、prim_prince 是抗故障注入的核心 |
| USB Full-Speed | 保留 FS 传输需求；优先评估 `usb_fs_nb_pe` + 精简 HID/EP0 包装，完整 `usbdev` 作成本对照 | 产品只需 12 Mbps FS；USB 2.0 Full-Speed 不代表 480 Mbps High-Speed。最小 PE 可避开完整控制器的 2 KiB SRAM/TL-UL/CSR，但端点控制与软件接口需补齐 |
| hmac | 产品路线候选 | FIDO2 PIN 协议、hmac-secret、固件度量可用 SHA-256/HMAC；是否纳入取决于功能矩阵与 PPA。HOTP 用的 SHA-1 走软件 |
| aes | 延后到有明确需求时 | 加掩码/不加掩码是不同安全等级与 PPA 选项；不能先以“放不下”代替实测 |
| keymgr | 换成 keymgr-lite | 保留"密钥绑定启动度量、软件拿不到根密钥、sideload 给 AES/HMAC"这个思路；KDF 用 HMAC-SHA256，不用 KMAC |
| otp_ctrl、lc_ctrl | 换成 eFuse-lite | 只保留 RAW/TEST/PROD/RMA 四个状态，用来控制 JTAG/调试和密钥可用性 |
| rom_ctrl | 简化 | ROM 用标准单元综合；启动前的 ROM 摘要检查视面积决定 |
| sram_ctrl | 保留思路 | PRINCE 加扰、每次上电换密钥、擦除；同一个 PRINCE 也用于外部 flash 的 XIP 解密 |
| alert_handler | 换成 alert-lite | 致命告警直接擦密钥并复位，不做 ping 和分级升级 |
| entropy_src、csrng、edn | 不整体移植；仅评估健康测试 | 上游完整链路依赖 AST 噪声源、CSRNG、EDN；GF180 环振方案需另做熵源和调理验证 |
| otbn、kmac | 去掉 | 见 2.3 |
| flash_ctrl、ast、pwrmgr、clkmgr、rstmgr、pinmux | 去掉 | GF180 没有嵌入式 flash；AST 是闭源模拟；时钟复位手写最小版 |
| rv_dm | 保留 | 调试的生命线，PROD 状态下由生命周期关闭 |
| spi_host | 可选 | 只有命令模式，没有 XIP；XIP 需要另写或引入 spimemio 一类的控制器 |
| ascon | 观望 | 面积小，适合做外部 flash 记录的 AEAD，但 IP 还在 D0/V0 |
| 软件 | DIF 复用，ROM 重写 | cryptolib 的非对称部分全部依赖 OTBN，用不上 |

顶层不用 topgen：它默认带 clkmgr/rstmgr/pwrmgr/AST，裁掉的成本比手写还高。USB 需求固定为 Full-Speed 12 Mbps；上游 OpenTitan `usbdev` 虽属于 USB 2.0 兼容设备，但它实现的是 Full-Speed，不是 High-Speed。P0 用 `usb_fs_nb_pe` 的无缓冲 64-byte 配置先做轻量综合基线，并将完整 `usbdev` 的 12 端点、2 KiB 包 RAM 和总线/CSR开销作为对照，不把协议引擎综合数当作完整控制器面积。

### 3.1 真实源码依赖与移植分类（以本地 `/Users/zxy/opentitan` checkout 为核对对象）

| 候选 | 上游实际存在的内容 | 必需依赖/集成工作 | 本项目决定与待验证项 |
|---|---|---|---|
| USB Full-Speed (`usbdev` / `usb_fs_nb_pe`) | 上游源码均明确为 USB Full-Speed；48 MHz 时钟。完整 `usbdev` 有 12 个端点、固定 `512×32 = 2 KiB` 包 RAM；`usb_fs_nb_pe` 是无缓冲协议引擎，端点数/最大包长可参数化 | 完整 IP 需 TL-UL、socket_1n、`prim:all`、edge detector、ram_1p_adv、CSR/reggen、RAM 宏适配、时钟复位/alert。PE 不含包 RAM、TL-UL、CSR，但需要补轻量 HID/EP0 与端点包装 | 需求锁定 12 Mbps FS，不需要 480 Mbps HS；先测 `usb_fs_nb_pe` 64-byte 配置作轻量基线，完整 `usbdev` 作为资源对照。两者都不含 USB 模拟 PHY，普通 pad 合规及有源 48 MHz 时钟仍待测 |
| `prim` | 多种通用 RTL 原语及 GF180 不存在的定制实现 | 必须筛选逐模块依赖，提供 GF180 RAM、同步器、时钟门控等映射；验证综合网表保留安全逻辑 | “复用 prim”不是零成本；每个选中的原语列入 lockfile/依赖清单并做网表核验 |
| AES | `hw/ip/aes` 完整多模式 RTL，依赖 `prim:all`、gf_mult、lc_sync、lfsr、onehot、sparse_fsm、trivium、TL-UL、LC/EDN/keymgr DPE package；包含 masking/PRNG 路径 | 若仅 AES-128 加密，需裁剪模式、寄存器、EDN/生命周期接口，并验证安全配置和综合结果 | 只有产品功能明确需要时纳入；“不加掩码”是安全降级设计选择，PPA与侧信道风险均需实测；FIDO2 HMAC 并不自动要求 AES |
| HMAC/SHA-2 | `hw/ip/hmac` 多模式 SHA-2/HMAC RTL；依赖 prim、TL-UL、keymgr DPE package | CSR/TL-UL、key sideload/wipe、时钟复位、软件驱动；需定制 keymgr 接口或明确 CPU 可见密钥路径 | SHA-256/HMAC 是 FIDO2 及派生候选；先与软件实现做 KAT/PPA 对照。将密钥直连且不可读是目标架构，不是已有 GF180 集成事实 |
| 熵 | `entropy_src` RTL 和健康测试模块确实存在；完整 IP 依赖 prim 计数器/边沿检测/LFSR/sparse FSM/max/sum tree/mubi 等 | 上游 entropy source 不是裸环振 TRNG；完整芯片还依赖 AST 噪声源、CSRNG、EDN 等系统组件。不能把健康测试模块当熵源或熵证明 | 环振采样方案是新设计假设；需明确 min-entropy 评估、偏差/相关性、环境与攻击条件，SP 800-90B 数据不足时不得用于密钥生成 |
| OTP/eFuse/lifecycle | OT OTP 控制器和 LC 控制器 RTL/package 存在，但不是 GF180 eFuse 编译器的即插即用驱动 | OTP macro、时序/电压、ECC/ scrambling、DAI、生命周期握手和制造流程均需平台适配；eFuse 编程电路可能需外部高压 | GF180 eFuse-lite 是自研候选；容量、读扰动、烧写良率、单调位可用性和断电行为待 P0/硅测；SRAM PUF 仅实验候选，不等价稳定根密钥 |
| Ibex / firmware | OpenTitan 使用 Ibex 与大量 SoC 支撑；本模板当前 `chip_core.sv` 仍是计数器示例，不含 CPU | 需核实 Ibex 独立 `ibex` FuseSoC core 及其 prim/存储器/中断/调试依赖；实现 ROM、RAM、启动、总线、定时器、异常/原子替代 | 不能根据 canokey-stm32 的 64 KB SRAM 或 512 B 专用方案推断移植后 RAM。对目标固件构建做 map/stack/heap 高水位和最坏路径测量；若 RAM 超预算，削功能或转较大 slot |

**真实实现 vs 设计选择 vs 假设：** 表中“上游存在”只表示源码可查，不表示已在 GF180 综合、时序、面积或硅上验证；`keymgr-lite`、eFuse-lite、alert-lite、XIP decrypt、`prim_gf180`、CPU 取舍是本项目新设计；普通 pad USB、电源/时钟、环振熵、SRAM PUF、512 B 工作区和任何面积百分比都属于待验证假设。需在版本表中记录 OpenTitan commit 与各 IP 来源。
`top_englishbreakfast` 只当参考。TO-A 和 TO-B 都手写顶层，只用 tlgen 生成 crossbar。

## 4. 关键技术问题

### 4.1 电压和单元库

- **全片 3.3V。** fd_io 把 IO 和 core 电源连在一起；ocd_io 要求 DVDD ≥ VDD。USB 要求 IO 是 3.3V，所以 core 也只能是 3.3V。
  板上用 LDO 从 VBUS 降到 3.3V。
- 标准单元用 mcu7t5v0 的 3.3V 角（PDK 里有 tt_025C_3v30 和 ss_125C_3v00）。这个角比 5V 慢。
  **P0 要确认 usbdev 的 48 MHz 逻辑在 ss_125C_3v00 下能否收敛。** 收不住就换 9t 库，或者缩小跑 48 MHz 的那部分逻辑。
  as_sc_mcu7t3v3 更快，但只经过仿真，不建议用于流片。

### 4.2 USB FS 物理层（最大的单点风险）

2026-11-16 边界修订：本节原先的普通 pad 直连是待验证假设；下一阶段的真实 cell 证据、
外置收发器优先评估路线与候选 pin 预留见 [PHY/I/O 方案](phy-io-plan.md)。

- 当前已检查的 fd_io cell list 未列 USB 收发器，本地未取得可用 USB PHY macro。PE 可输出数字 DP/DM，或选择单端采样模式；这不证明两个普通双向 pad 满足 USB FS 电气要求。直连只作为待 SPICE/封装/板级验证的实验路线，优先评估匹配 PE 数字接口的外置 FS 收发器。
- 驱动阻抗：USB FS 要求 28~44 Ω（含外部串阻）。P0 用 PDK 里 pad 的 SPICE 网表仿真，定外部串阻（预计 22~33 Ω）和 slew 设置，再对照 USB FS 眼图模板检查。
- D+ 上拉：候选为外部 1.5 kΩ 配合可关断的 3.3V 上拉/开关，不用 pad 内部弱上拉。当前 P0 PE 没有 `usb_dp_pullup_o`；需新增 link/attach manager 和板级控制，核对 GPIO 驱动、上电、断电反灌与 VBUS 时序。
- 时钟：USB FS 要求 ±0.25%，开源 GF180 没有能用的 PLL。v1 用外部 48 MHz 有源晶振，二分频得到 24 MHz 给 CPU。
  usbdev 的 `usb_ref_val_o`/`usb_ref_pulse_o` 以后可用于无晶振校准。
- 退路：TO-A 实测电气不过关，TO-B 就外接 USB FS 收发芯片，usbdev 改用 D/SE0 发送模式和外部差分接收输入。

### 4.3 非易失存储、根密钥和防回滚

- 片上没有 flash，代码和 littlefs 都放外部 QSPI NOR（≥16 Mbit）。
- 根密钥放 eFuse：出厂时由片上 TRNG 生成并烧入，软件读不到，只能经 keymgr-lite 派生使用。
  eFuse 编译器还没有硅数据，所以 TO-A 同时做 SRAM PUF 实验作为备选。
- 外部 flash 上的数据用 keymgr-lite 派生的密钥加密并认证，与芯片绑定。canokey-stm32 的 littlefs 是明文。
- **防回滚是最难的一点。** 攻击者可以备份 flash，试 PIN，再写回备份，把重试计数复原。候选方案：
  1. eFuse 单调计数器：每次比对 PIN 前先烧 1 bit，flash 里记一个基线，剩余次数 = 上限 −（已烧位数 − 基线）。
     写回旧的 flash 镜像只会让剩余次数变少。代价是 eFuse 总位数限制了整个寿命内的 PIN 验证次数。
     如果只在失败时烧，又要防"比对后、烧录前断电"。
  2. 选用带 RPMC（重放保护单调计数器）的 SPI NOR。
  3. 接受这个风险，写进威胁模型。

  P0 结束前要定下来。

### 4.4 TRNG

- 没有模拟噪声源，用几组自由振荡的环振，采样后异或得到原始比特。
- 健康测试复用 `hw/ip/entropy_src/rtl/entropy_src_repcnt_ht.sv` 和 `entropy_src_adaptp_ht.sv`。
- 调理和 DRBG：TO-B 用硬件 HMAC 跑软件 HMAC-DRBG，不引入 SHA3 和 AES-DRBG。
- 环振要防止被综合优化掉：用实例化的单元加 keep 属性。流片前用 SPICE 和门级仿真确认能起振；熵率回片后按 SP 800-90B 实测。

### 4.5 安全启动和 XIP

- 不可改的 ROM 依次做：初始化，读 eFuse 生命周期，校验外部 flash 上固件的签名（公钥哈希在 eFuse 里），
  把签名者公钥哈希和安全版本号送进 keymgr-lite，然后跳转。
- 密钥派生绑定"签名者 + 安全版本号"，不绑定镜像哈希。否则每次升级都会丢掉已有凭据。
- **XIP 的 TOCTOU 问题**：校验完以后 CPU 仍从外部 flash 取指，攻击者可以在校验后换片。
  缓解办法：外部 flash 内容用设备密钥加密，以地址作 tweak（和 sram_ctrl 同一思路），取指时在线解密。
  拿不到密钥就造不出有意义的代码。这只提高门槛，不保证完整性，要写进威胁模型。
- ROM 面积：Ed25519 或 ECDSA 验签代码约 8~12 KB。放不下就退成"eFuse 设备密钥 + HMAC 校验"，
  代价是固件一旦被攻破，就能给恶意镜像算出合法的 HMAC。

### 4.6 RTL 移植和后端流程

- 前端：先试 LibreLane 的 `USE_SLANG`（模板 `librelane/config.yaml` 里已有注释）。不行就走 sv2v + Yosys，参考 Ibex 的 `syn/` 流程。文件列表由 fusesoc 从 `.core` 导出。
- 新建 `prim_gf180`，照 `hw/ip/prim_asap7/rtl` 的模式写：buf、flop、xor/and、clock gating 都映射到具体的 GF180 单元并加 keep。
  不这样做，Yosys/ABC 会把稀疏编码、mubi、冗余副本这些加固逻辑优化掉。
  `prim_ram_1p` 映射到拼接的 OCD SRAM 宏；`prim_rom` 综合成 case 语句。
- SDC：模板只约束一个时钟。要改成 48 MHz 输入时钟加 24 MHz 生成时钟，并约束 usbdev 的异步跨时钟域。
- 网表检查：门级仿真抽查；sv2v 的输出可参照 Ibex `syn/lec_sv2v.sh` 做等价性检查。

## 5. 固件：移植 canokey-core

canokey-core 的移植边界很清楚：

| 接口 | 实现 |
|---|---|
| USB 层 `USBD_LL_*`（Init、OpenEP、Transmit、PrepareReceive、StallEP、SetUSBAddress 等） | 在 OpenTitan usbdev DIF 上实现。需要 EP0、FIDO HID、CCID、WebUSB、键盘 HID，12 个端点够用 |
| `device.h`：delay、get_tick、set_timeout | rv_timer |
| `device.h`：spinlock、atomic CAS | Ibex 没有 A 扩展，单核关中断实现 |
| `device.h`：LED、touch | GPIO |
| `rand.h` | TRNG + DRBG |
| littlefs 块设备 | QSPI NOR，中间加一层加密和认证 |
| canokey-crypto | 对外函数是弱符号，可以逐个用硬件覆盖。SHA-256/HMAC/AES 走硬件，ECC 走软件；ML-DSA/ML-KEM 占 RAM 太多，关掉 |

- RSA：软件 RSA-2048 签名在 Ibex 上预计要几秒，生成密钥更久。v1 的 OpenPGP/PIV 只开 ECC（P-256、Ed25519/X25519）。
- RAM 预算：canokey-core 的 dev 分支在 `DESIGN.md` 里明确针对"小 RAM、有界栈、无 heap"设计。
  P3 在 QEMU/FPGA 上实测各功能组合的 RAM 峰值，再定 TO-B 是 24 KB 还是 32 KB。

## 6. 验证

- 没改动的 OpenTitan IP（usbdev、aes、hmac、Ibex）沿用上游 DV 的结论，不重建 UVM。
- 改过的和新写的模块（SPI 桥、TRNG、eFuse-lite、keymgr-lite、alert-lite、XIP 解密）写定向测试。
- 系统级：Verilator 加 OpenTitan 的 USB 主机模型（`hw/dv/dpi/usbdpi`），跑枚举和 CTAPHID；整片用模板现有的 cocotb。
- FPGA：Arty A7-100T 或 CW305（`top_englishbreakfast` 有 CW305 的目标可以参考）。
  USB 用 3.3V IO 加串阻直连 D+/D-，和芯片的接法一致，提前验证单端接收。在 FPGA 上跑 canokey-core 的 FIDO2 一致性测试和 PC/SC 测试。

## 7. 阶段计划

| 阶段 | 时长 | 内容 | 退出条件 |
|---|---|---|---|
| P0 标定 | 2 周 | nix-shell 跑通模板；用 GF180 3.3V liberty 综合 Ibex、usbdev、hmac、aes 和一个 8 KB ROM；48 MHz STA；USB pad SPICE；试 slang/sv2v；测可达的布局利用率；试做短边 pad 环 | 第 2 节的估算换成实测；定下 slot、TO-A 范围、SRAM 库、时钟、防回滚方案 |
| P1 骨架 | 3~4 周 | `prim_gf180`、手写顶层 + tlgen；TO-A 的 SPI 桥、TRNG、eFuse-lite | Verilator 里 USB 枚举成功；LibreLane 跑完，DRC/LVS 干净 |
| P2 TO-A 流片 | 2~3 周 | 物理实现、gf180mcu-precheck、门级仿真、测试板设计 | GDS 提交 |
| P3 固件 | 2~4 个月，与 P2 并行 | canokey-core 移植到 FPGA（Ibex + usbdev），顺序是 FIDO2/U2F → OATH → OpenPGP/PIV（ECC） | FPGA 上通过 FIDO2 一致性测试；RAM 峰值实测 |
| P4 TO-B 设计 | 3~6 个月 | SecureIbex、HMAC/AES、keymgr-lite、eFuse 生命周期、安全启动 ROM、XIP 解密、alert-lite | FPGA 上全功能通过；面积和时序收敛；赶下一班 GDS 截止 |
| P5 TO-A 回片 | 回片后（Run 3 为 2027 Q2） | USB 眼图和枚举、TRNG 熵率、eFuse 烧写良率、PUF 稳定性 | 结论回灌 TO-B |

**赶 Run 3 的话**：P0+P1+P2 正常要 7~9 周，压缩到 40 天只能做 TO-A 的最小集合（usbdev + SPI 桥 + TRNG + eFuse），
而且要在 12-09 前买 slot。来不及就等下一班。

## 8. 风险

| 风险 | 后果 | 缓解 |
|---|---|---|
| GF180 普通 pad 达不到 USB FS 电气要求 | 单芯片方案不成立 | P0 SPICE、外部串阻、TO-A 实测；退路是外接收发器 |
| 面积估算偏差 ±30~50% | TO-B 放不下 | P0 实测；按 2.3 的顺序砍 |
| eFuse 没有硅数据 | 根密钥和生命周期没着落 | 跟进 Run 1 测试片结果；TO-A 实测；SRAM PUF 作备选 |
| OCD SRAM 只部分经过硅验证 | 存储出错 | 片上 MBIST；TO-A 先用起来 |
| 综合工具优化掉加固逻辑 | 抗故障注入能力失效 | `prim_gf180` 实例化 + keep；检查网表 |
| OpenTitan 的 SV 写法前端不支持 | 流程卡住 | slang 优先，sv2v 兜底，门级仿真对照 |
| 7t 库 3.3V 下 48 MHz 收不住 | usbdev 不工作 | P0 STA；换 9t 或缩小 48 MHz 域 |
| 外部 flash 被回滚或替换、XIP TOCTOU | PIN 被暴力破解、代码被替换 | eFuse 单调计数器、在线解密；剩余风险写进威胁模型 |
| 软件 RSA 太慢 | OpenPGP/PIV 体验差 | v1 只开 ECC |
| Run 3 只剩 40 天 | 仓促出错 | 只做最小 TO-A，或者放弃这一班 |

## 9. 威胁模型（初稿）

- **防**：恶意主机（USB 协议层的攻击）；固件替换（安全启动）；离线读外部 flash（加密并与芯片绑定）；简单的故障注入（OpenTitan 的加固原语、SecureIbex）。
- **不防**：物理探针、直接读出 eFuse、功耗和电磁侧信道。AES 不加掩码；软件 ECC 只能尽量做到恒定时间。
- 对照：canokey-stm32 的 README 写明"任何能物理接触的人都能取出全部数据，包括私钥"。
  TO-B 的目标是堵上这个口子，不追求 CC EAL 一类的认证级别。

## 10. 需要你拍板的问题

1. **预算**：quarter slot 是不是硬约束？如果是，能做的产品形态有三种：
   (a) GF180 只做 USB + TRNG + 根密钥，外接 MCU 跑 canokey-core。安全性取决于那颗 MCU；
       除非芯片里加 KDF，否则 MCU 能经 SPI 直接读到根密钥。
   (b) 见第 4 点。
   (c) 第 11 节的全专用 U2F 芯片：只有 U2F，但单芯片，也不需要外部 flash。
2. **要不要赶 Run 3**：12-09 前买 slot，12-16 前交 GDS，只能做最小 TO-A。
3. **v1 功能范围**：只做 U2F（适合第 11 节的全专用路线），还是要 FIDO2 的 PIN/passkey，或者 OpenPGP/PIV/OATH（需要 CPU）？RSA 要不要？
4. **封装**：wafer.space 的 COB 必须用默认 pad 环。如果自己邦定，quarter slot 可以只在两条短边放 pad，core 约 3.0 mm²（见 11.5）。
   这时方案 C 中值只占约 38%~45%；2.1 节带 CPU 的方案也放得下（约 56%~82%），但片上只有 1 KB RAM，仍然跑不了 canokey-core。

## 11. 全专用化评估（方案 C：专用 U2F 芯片）

问题：能不能去掉 CPU 和固件，把所有功能都做成专用硬件？

### 11.1 结论：只对 FIDO U2F 成立

U2F（CTAP1）适合专用化，原因有三：
- **协议冻结**：U2F 1.2 之后不再演进，并入 CTAP 规范成为 CTAP1。浏览器经 WebAuthn 仍支持只会 CTAP1 的设备。
- **不需要存储**：私钥由"设备密钥 + key handle"派生，芯片里只要一把 eFuse 设备密钥。
  签名计数器可以恒为 0：WebAuthn 规定双方计数器都为 0 时，依赖方跳过检查。
- **计算固定**：只有 P-256 ECDSA、SHA-256、HMAC，指令只有 REGISTER、AUTHENTICATE、VERSION 三条。

不适合专用化的：OpenPGP、PIV、OATH、CTAP2 passkey。它们本质上是"协议 + 小数据库"：
指令多，TLV/CBOR 是变长的，要存多把密钥和证书。硬写成状态机，面积和验证成本都比一颗小 CPU 大，
而且照样要外部 flash，第 4.3 节的回滚问题也还在。

### 11.2 架构

全片只有一个 48 MHz 时钟域，ECC 和 SHA 用 24 MHz 使能。没有 CPU、总线和固件，只有 ROM 里的常量和微码。

| 模块 | 做法 | 来源 |
|---|---|---|
| USB FS | `usb_fs_nb_pe`（rx/tx/in_pe/out_pe）配 2 个端点、64 字节包；EP0 枚举状态机 + 描述符 ROM | 复用 usbdev 内部协议引擎，外加新写 |
| CTAPHID + U2F | 请求解析和响应拼装都由 ROM 段表驱动：常量、scratchpad 字段、长度、DER 编码 | 新写 |
| SHA-256 / HMAC | 沿用 `prim_sha2` 的轮函数和常量（只走 32 位路径），W 和 digest 改放 scratchpad，只有 a~h 留在触发器 | 部分复用 |
| P-256 引擎 | 16 位蒙哥马利乘累加器 + 微码序列器 + 常量 ROM，多字中间量放 scratchpad（8 位宽，一个 16 位字读两拍）；co-Z 蒙哥马利阶梯，费马求逆；签名 nonce 按 RFC 6979 确定性生成，不依赖 TRNG | 新写，相当于缩小到一种曲线的 OTBN |
| TRNG | 环振 + `entropy_src` 的健康测试；只用于 key handle 的 nonce 和出厂生成设备密钥 | 复用健康测试 |
| 设备密钥 | eFuse，只接到 HMAC 的密钥端口，任何输出口都读不到 | 新写，用 prim 加固原语 |
| 用户在场 | 按键消抖后锁存；没按就回 0x6985，主机会重试 | 新写 |

流程：
- **REGISTER**：nonce（16 B）← TRNG；私钥 = HMAC(设备密钥, app‖nonce) mod n；key handle = nonce‖MAC 前 16 B，共 32 B；
  算公钥；用 ROM 里的批量 attestation 私钥对注册数据签名，attestation 证书也是 ROM 里的固定字节。2 次标量乘。
- **AUTHENTICATE**：重算 key handle 的 MAC，恒定时间比较，不对就回 0x6A80；对了再派生私钥并签名。1 次标量乘。
- **出厂自举**：TRNG 输出经健康测试和 SHA-256 调理后烧进 eFuse，校验后烧 PROD 位并关闭测试口。
  如果 eFuse 烧写要外部高压，这一步放在出厂测试夹具上做。

### 11.3 存储：用什么存、存多少

**每 bit 面积**（由 GF180 7t 单元和 OCD SRAM 的 LEF 尺寸换算，含布局利用率）：

| 存储方式 | 每 bit 面积 | 适合放什么 |
|---|---|---|
| 综合 ROM | 约 6~13 µm²（推算） | 只读常量。综合成组合逻辑，越大越省，有规律的数据更省 |
| OCD SRAM 宏 | 边际 14.3 µm²，另加每片固定约 0.039 mm² | 可写数据。1024×8 合 19 µm²/bit，512×8 合 24，64×8 合 90 |
| 锁存器阵列（DFFRAM 式手工摆放） | 约 80~105 µm² | 小的可写缓冲。DFFRAM 目前不支持 gf180mcuD（网表有 hold 违例） |
| 触发器（自动布局布线） | 约 180~230 µm²（含读 mux） | 当拍要用的寄存器 |
| eFuse | 约 100 µm²（只算阵列） | 一次性写入：设备密钥、生命周期位 |
| 自研 DRAM（MIM 电容或增益单元）、via-ROM | 理论上 2~6 µm² | 不建议 v1：全定制模拟设计，没有硅数据 |

- 可写数据里 SRAM 已经最省：触发器每 bit 是它的 7~12 倍，锁存器阵列是 3~5 倍。
  例：`prim_sha2` 原样有 1,024 个数据触发器（hash 256 + W 512 + digest 256），约占 quarter core 的 10%；放进 SRAM 只要 128 字节。
- sky130 上 DFFRAM 的数据是同一方向：1 KB 时 OpenRAM 宏 46,541 bit/mm²，DFFRAM 26,027，RTL 走 OpenLane 7,360。
  GF180 的标准单元相对 SRAM 更大，差距只会更大。
- 一片 SRAM 宏的固定开销约 0.039 mm²（相当于约 2 kGE 逻辑），大约等于二三十字节的触发器。所以小于这个量的状态用触发器，
  其余全部进 SRAM，而且只用一片：已经有一片宏时，再往里放数据只付边际成本。
- 综合 ROM 每 bit 比 SRAM 还省，也没有固定开销。这个数是按 MUX2 树推算的，P0 要实测。前提是数据真是常量。
- OpenRAM 有 gf180mcu 工艺目录，可以生成别的形状（比如 32 位宽），但没找到硅数据，v1 不用。

**结论：没有比 SRAM 更省的可写存储可以替换它，能省的是"少存"。** 做法：

1. **常量全部放综合 ROM，从不拷进 SRAM**：USB 描述符、SHA-256 的 K 常量和初值、P-256 常数（p、n、b、G、R²）、ECC 微码、
   CTAPHID/U2F 响应模板，合计约 1.5~2 KB，已经算在逻辑面积里。
2. **attestation 改用 ROM 里的固定证书和批量私钥**：省 1 次标量乘、一个 72 B 的签名缓冲和证书拼装逻辑。代价见 11.6。
3. **USB 零拷贝**：OUT 包的字节直接写到请求字段的最终地址，CRC 错或主机重发就把写指针退回包头；
   IN 数据直接从 ROM 或结果区读，重发就重读同一地址；CTAPHID 包头、DER 长度字节、状态字由逻辑现场生成。不设包缓冲。
4. **现场生成代替存储**：设备密钥从 eFuse 直接读进 HMAC，K⊕ipad 和 K⊕opad 现场异或；SETUP 包边收边解析到几个触发器里。
5. **按生命周期复用地址**：SHA 的 W、HMAC-DRBG 的 K 和 V 用完就让给 ECC 的域寄存器；k⁻¹ 在阶梯释放出的空间里算。
   相当于在设计时给每个变量做一次寄存器分配，结果写成微码里的地址表。
6. **缩短数据**：key handle 用 16 B nonce + 16 B MAC，共 32 B，128 位安全，不用 64 B。

**512 B 是否够**：REGISTER 是最坏情况；下表只是待实现的活跃区间草图。ECC 工作区 = 6~8 个 32 B 域寄存器 + 36 B 蒙哥马利累加器的假设必须由微码、RTL 仿真和断言确认，不能称为已验证容量。

| REGISTER 阶段 | 同时存活的数据 | 字节 |
|---|---|---|
| 收请求、派生私钥 | challenge 32、app 32、nonce 16、SHA 的 W 64 和 H 32、HMAC 中间值 32 | 208 |
| 算 Q = d·G | challenge、app、key handle 32、d 32、ECC 工作区 228~292 | 356~420 |
| 算 e，按 RFC 6979 生成 k | key handle、Q 64、e 32、K 和 V 64、SHA 96、中间值 32 | 320 |
| 算 R = k·G（峰值） | key handle、Q、e、k 32、ECC 工作区 | 388~452 |
| 算 s | key handle、Q、e、k、r 32、求逆工作区 96 | 288 |

峰值 388~452 B，一片 512×8 留 12%~24% 余量，AUTHENTICATE 的峰值更低。装不下就换 1024×8，多 0.058 mm²（约 3.4% core）。
布局时先按 1024×8 留位置，微码定稿后再定。

**代价**：
- SRAM 只有 8 位宽、单口。SHA 每块约 1,300 周期，ECC 一次模乘约 1,650 周期。时间大头是标量乘，总时间见 11.4。
- 所有模块共用一片 SRAM，要一个仲裁器（USB 优先；收发和计算本来不同时进行，所以很简单）和各模块的字节拼装寄存器，逻辑多约 1 kGE。
- 两个可选方向：SHA 的 a~h 也放进 SRAM，再省约 0.02 mm²，SHA 慢 3 倍，对总时间影响很小；
  反过来，ECC 累加器放回触发器，多约 0.05 mm²，标量乘快 2~3 倍。

### 11.4 面积和性能（估算）

| 模块 | 直接拼现成模块（kGE） | 状态放 SRAM，2 KB（kGE） | 存储最小化，512 B（kGE） |
|---|---|---|---|
| USB FS 引擎（PE + EP0 + 描述符） | 9~15 | 9~14 | 9~14 |
| CTAPHID + U2F 状态机（含证书 ROM、DER 编码） | 6~12 | 5~10 | 5~10 |
| SHA-256 + HMAC | 14~21 | 8~12 | 8~12 |
| P-256 引擎 | 12~20 | 7~11 | 7~11 |
| TRNG、eFuse、生命周期、时钟复位、按键、LED | 8~15 | 6~12 | 6~12 |
| 测试口（SPI，PROD 状态关闭） | 3~5 | 3~5 | 3~5 |
| SRAM 仲裁和字节拼装 | — | — | 1 |
| **逻辑合计** | **52~88** | **38~64** | **39~65** |
| SRAM 和 eFuse（mm²） | 1 KB + USB 缓冲 + eFuse：0.36~0.41 | 2×1024×8 + eFuse：0.39~0.44 | 1×512×8 + eFuse：0.16~0.21 |
| **占 quarter core（低 / 中 / 高）** | **81% / 113% / 151%** | **66% / 90% / 118%** | **54% / 78% / 106%** |

换算用 0.020~0.025 mm²/kGE，对应 55%~60% 利用率，另加 10%~15% 的时钟树、hold 缓冲和 tap 单元；SRAM 宏另加 10% halo。

- 旧版估算的用途仅是排序风险：直接拼现成模块和最小化存储两组方案都需 P0 综合/物理实现验证；中值百分比和“放得下”概率不构成承诺。最坏情况超限时，按功能削减、增大 SRAM 或改用 1×0.5 slot 决策。
- 剩下的不确定性：GF180 + LibreLane 实际能到多少利用率；Yosys 结果比手算大多少；综合 ROM 实际多大；
  新写的 P-256 引擎和协议状态机实际多大；需求膨胀（某平台必须要 CTAP2，就要再加 10~20 kGE）。前三项不用等新设计，P0 就能量出来。
- 文献里一个紧凑 ECDSA 引擎是 11,366 GE，和上面 P-256 引擎的估算是同一量级。
- 性能（24 MHz，8 位宽 SRAM）：ECC 累加器放 SRAM 时，一次标量乘约 0.2~0.3 秒，REGISTER（2 次标量乘）约 0.5 秒，AUTHENTICATE 约 0.3 秒。
  累加器放触发器（多约 0.05 mm²）：标量乘约 0.1 秒，REGISTER 约 0.2 秒，AUTHENTICATE 约 0.1 秒。
- BOM：die、48 MHz 有源晶振、3.3V LDO、USB 口、串阻和上拉电阻、按键、LED。不需要外部 flash。

### 11.5 布局优化（待验证的几何假设）

依据：`librelane/slots/slot_0p5x0p5.yaml` 的 die 尺寸（1936×2531 µm，含 26 µm 封环）、IO 单元 75×350 µm、
模板里 ID 宏（左下角）和 marker（右上角）的位置。模板默认的 pad 环每边占 442 µm：封环 26、pad 350、pad 到 core 66（放 25 µm 宽的 core 电源环）。

| 措施 | 收益 | 前提和代价 |
|---|---|---|
| 布局利用率 55% → 65%（乐观 70%） | 逻辑面积 −15%（−21%） | 模板的 hold 修复余量是 0.35/0.3 ns，可降到约 0.1 ns；PDN 条带（现为 5 µm 宽、75 µm 间距）改细改疏，给 Metal4/5 腾出布线；SRAM 宏放角上。能到多少只能 P0 实测 |
| core 电源环 25 µm → 15 µm | 理想矩形 core 约 1.733 → 1.787 mm²（+3.1%） | 假设 core 边界可四边各外移 10 µm；必须检查 pad 间距、PDN/IR/EM、DRC 及封装/模板要求；电流承载尚未验证 |
| 自定义 pad 环：只在两条短边放 pad | core 面积待重算；3.03 mm² 尚非模板可直接推出的数值 | 不能用 wafer.space 的 COB 封装和转接板，要自己邦定（USB key 本来就是 COB 上板）。两条短边共约 41 个 pad 位，方案 C 要 16~19 个 |
| 只在两条长边放 pad | core → 2.62 mm²（+51%） | 不如放短边 |
| 只在一条短边放 pad | core → 3.60 mm²（+108%，已扣掉 marker 占的角） | 只剩约 20 个 pad 位，电源和 ESD 都紧，不推荐 |

wafer.space 的 logo 可以删，但它在角上，不占 core，删了没有收益。

**方案 C（512 B SRAM）的结果**（占 core 的比例，低 / 中 / 高）：

| 布局 | core | 利用率不变 | 利用率调到 60~70% |
|---|---|---|---|
| 模板默认 | 1.73 mm² | 54% / 78% / 106% | 48% / 66% / 87% |
| 默认 pad 环 + 15 µm 环（理想矩形外扩模型） | 1.787 mm² | 约49% / 72% / 97%* | 约43% / 60% / 74%* |
| 两条短边 pad + 15 µm 环 | 暂不定值 | 暂不定值 | 暂不定值 |

此表仅是面积除法的敏感性分析，不能视为布局结果；上一版 1.87 mm² 和 3.03 mm² 不由 slot YAML 的几何直接推出。*新增比例按方案 C 逻辑区面积不变、只增加 core 面积粗略重算；宏面积、halo、利用率定义及固定布局障碍必须在 P0 统一口径后重算。

- 暂不据此宣称方案 C 已能放入 quarter slot。几何仅给理想 floorplan 上限，实际 core 可用面积须扣除宏、marker/ID、tap/endcap、PDN、布线和 keepout。
- 默认 pad 环是 wafer.space 模板与默认 breakout 的已知接口；改 pad 排布/位置可能失去 COB/转接板兼容，需向 shuttle 运营方确认，不能由“自己邦定”自动推得。
- P0 前不把短边 pad 方案纳入基准产品面积；另开实验 floorplan，只有 padring、ESD、封装与 signoff 逐项通过才更新预算。
- 多出来的面积先留作余量。要用的话，按这个顺序：
  1. ECC 累加器放回触发器：+0.05 mm²，标量乘快 2~3 倍。
  2. 给第一版硅加调试通路：非 PROD 状态下经 SPI 读内部状态。
  3. 最小 CTAP2 子集：+10~20 kGE（约 0.2~0.4 mm²），短边 pad 环下最坏情况约 63%，放得下；但 CBOR 硬件解析的设计和验证量很大。
- 要验证的事：
  - LibreLane 的 PadRing 步骤能不能只在两边放 pad，不行就自己写摆放脚本。用 `make librelane-padring` 先试。
  - 两段 pad 之间的 ESD 通路，要查 IO 库文档。
  - 15 µm 电源环要过 IR drop 和电迁移检查（模板里有 IR drop 报告步骤）。

### 11.6 得失

得：
- 没有固件，就没有代码注入。设备密钥只连到 HMAC 的密钥端口。
- 没有外部 flash，第 4.3 节的回滚问题和第 4.5 节的 XIP TOCTOU 都不存在。
- ECC 阶梯的操作序列是固定的，恒定时间由结构保证。模乘最后的条件减法要用"都算、mux 选"的写法。
- 单时钟域，时序和跨时钟域都简单。

失：
- 没有 OpenPGP、PIV、OATH；没有 CTAP2 的 PIN/UV 和常驻凭据，所以只能当二步验证用，不能做无密码的 passkey 登录。
- 协议 bug 在硅上改不了，只能重新流片。
- attestation 用 ROM 里的固定证书和批量私钥。GDS 是开源的，这把私钥等于公开，所以 attestation 不提供任何信任，
  过不了要求 FIDO 认证 attestation 的依赖方（大多数网站默认要 "none"）。好处是所有芯片共用一张证书，没法靠它跨网站关联用户。
- 签名计数器恒为 0，没有克隆检测。要的话，外加一颗 I2C EEPROM 和一个小状态机。
- 设备密钥不能备份，用户要注册两把钥匙，和其他硬件钥匙一样。
- 不防功耗和电磁侧信道。AUTHENTICATE 让攻击者可以反复提交自选的 key handle，对 HMAC 做 DPA。
- 要在 FPGA 阶段实测 Safari/iOS 和 Windows 对只会 CTAP1 的设备的支持。
  如果某个平台必须要 CTAP2，就要加一个最小 CTAP2 子集（CBOR），估计再加 10~20 kGE，quarter slot 就放不下了。

### 11.7 验证要求更高

硅上没法打补丁，所以：
- 签名 nonce 用 RFC 6979，签名可以和公开的 P-256/SHA-256 测试向量逐位比对，再用 OpenSSL 验签。
- FPGA（Arty A7）上用 python-fido2、libfido2 和真实浏览器，跑注册和登录。
- 用 SymbiYosys 证明三条性质：设备密钥不会出现在任何输出上；没有用户在场就不签名；key handle 的 MAC 不对就不派生私钥。

### 11.8 对计划的影响

工作量：新写 P-256 引擎和两套协议状态机，再集成，一个熟练的人做到 FPGA 跑通约 3~4 个月。赶不上 Run 3。

建议路线：
1. Run 3 照常做 TO-A。它验证的 USB 协议引擎、TRNG、eFuse 和 OCD 512×8 SRAM 宏，正是方案 C 要复用的部分，等于提前给方案 C 排雷。
2. 下一班用 quarter slot 做方案 C，作为第一款产品。
3. 需要 OpenPGP/PIV/OATH/passkey 时，再做 1×1 的 TO-B。方案 C 的 P-256 引擎可以直接放进 TO-B，
   替代 OTBN 在 P-256 上的角色：比软件 ECC 快，恒定时间也由硬件保证。


## 12. 执行计划、阶段门槛与面积预算（v0.4）

### 12.1 面积口径

每个候选配置统一同时报告：综合 cell area、宏 GDS/LEF footprint、floorplan core area、占用率/目标密度、PDN 与宏 halo/keepout、CTS/hold 修复后面积、可布线/DRC 后面积。禁止把 `kGE × 一个固定系数` 的估算直接称作可实现面积。方案 C 在当前 quarter core 的占比暂仅沿用 11.4 的低/中/高估算作风险筛选；短边 pad 和收窄电源环方案都标为未验证。

P0 的预算样本至少包括：

| 用途 | 内容 | 面积/预算处理 | 退出条件 |
|---|---|---|---|
| 组合 A：基准 0.5×0.5 | 最小 USB 控制/桥接 + 512×8 OCD SRAM + 实际电源/测试接口 | 以综合 cell area + 宏 footprint + 实际 floorplan 统计，不预填预测值 | LibreLane 完整跑通；宏识别、PDN、STA、DRC/LVS 可检查 |
| 组合 B：专用 U2F 512 B | USB、SHA/HMAC、P-256、微码/ROM、eFuse 接口、1×512×8 SRAM | 逻辑与 ROM 分开报告；宏 footprint 取本次选定 PDK LEF | RTL 测试向量正确；512 B 生命周期峰值经静态分配/断言证明 |
| 组合 C：专用 U2F 1024 B | 同 B，工作 SRAM 增至 1×1024×8 | 比 B 增量按实际宏 LEF 和 PDN 更新，不能预设只增 0.058 mm² | 与 B 同条件 PPA 比较，保留可解释余量 |
| 组合 D：布局/PDN 敏感性 | 默认 core；15/25 µm core ring；默认及试验 pad 排布 | 每个 run 保存配置、面积、拥塞、IR/EM、DRC/LVS；不把 60–70% 目标密度当作实际利用率 | 至少一个默认兼容方案通过全部物理检查 |

产品候选在 P1 的硬门槛：最坏 corner STA 有正 slack 并含时钟不确定度；宏与 PDN 连接无未解释告警；DRC/LVS 通过；routing 无不可接受拥塞；方案 C 面积还需留至少 20% core 空间作为早期余量（这是项目决策门槛，不是工艺规则）。若基准方案未过，不以提高 density 或扩大理想 core 算术来替代缩减功能/改 slot。

### 12.2 分阶段执行

| 阶段 | 具体工作 | 验证产物 | Go/no-go 决策 |
|---|---|---|---|
| P0a：资料与基线（1 周） | 锁定 wafer.space 本次 run/slot 文档与模板 commit；确认 pad ring、bonding、ESD、供电、测试与交付约束；对 OpenTitan 固定 commit 建立子集清单 | 来源链接/版本表、RTL/IP 依赖图、风险登记册 | USB PHY、SRAM、电源或封装存在硬阻断时，先改产品边界 |
| P0b：可综合性和 PPA（1–2 周） | 在当前模板以 0.5×0.5、3.3V 库执行最小 top；分别跑 7t/9t、候选 SRAM；检查 SRAM 端口/时序/电压；比较 slang 与 sv2v；按真实 SDC 跑 STA | 综合报告、宏清单、时序报告、面积分解、可复现配置 | 决定 TO-A/专用 U2F/CPU 产品路线和 SRAM 深度 |
| P0c：物理可行性（1 周） | 先按模板默认 pad 做完整 padring 与全流程；独立试验 15 µm ring 和自定义 pad；做宏放置、PDN/IR/EM、拥塞、DRC/LVS | GDS/报告和差异表；记录每种约束的来源 | 只有兼容性及 signoff 验证通过的方案才进入基准面积预算 |
| P1：RTL 子系统（3–6 周） | 固定 IP commit；裁剪必要 prim/usbdev；实现 GF180 宏适配、复位/时钟、测试通路；先做模块仿真，再集成 | lint/elaboration、定向回归、等价性或参考模型比对 | 协议/密码核心功能正确且接口冻结才进 P2 |
| P2：候选流片冻结（2–4 周） | 全 corner STA、CDC/RDC、门级仿真、预检、封装 pinout/板卡、可复现 GDS | signoff checklist、GDS checksum、制造交付文件 | 所有关键红项关闭；明确已知限制後提交 |
| P3：硅后验证 | 先测供电/时钟/IO，再 USB 眼图与互操作、SRAM、TRNG/eFuse（若纳入）及故障注入基础行为 | 可复现测试程序与原始测量数据 | 以实测结果决定下一版，不从单颗样片推断良率/认证 |

时间表、报价、Run 截止日会变动；执行 P0a 时从官方当前页面重新确认。原文日期仅代表 2026-11-06 草案的当时记录，不应用于当前采购决策。

## 13. P0 可执行验证清单与 go/no-go

所有步骤在当前代码仓和已安装工具环境中执行并归档原始报告；每项记录工具版本、OpenTitan commit、约束文件、命令、退出码与产物。不得用手算面积替代流程结果。

1. **P0a：冻结物理与产品输入（1–2 天）**：从 wafer.space 官方当前 run 页面下载/记录 0.5×0.5 默认 pad/COB 文件及 1×0.5 备选文件、pad 规则、供电和 GDS 截止；与本仓 `librelane/slots/*.yaml` 对照。冻结首版用户功能矩阵（U2F-only 或 CTAP2 具体子集）、按键/LED、测试接口、USB 供电、固件是否可更新及 PIN 防回滚威胁模型。
2. **P0b：RTL 可移植性**：固定 OpenTitan commit；用 FuseSoC/Edalize 从 `usbdev.core`、`aes.core`、`hmac.core` 和 entropy 健康测试 core 导出依赖闭包，生成依赖清单。先跑 elaboration/lint，再试 LibreLane slang；若失败才试 sv2v/Yosys，并保留错误日志。明确区分通过上游 DV 与本地改动后重新验证的模块。
3. **P0c：可综合性/PPA**：建立独立综合 top：USB FS PE 轻量基线（64-byte packet）、完整 usbdev（含原 2 KiB buffer，记录其依赖闭包阻塞）、HMAC-SHA256、候选 AES-128；额外综合 Ibex 最小配置和实际启动 ROM 仅作为产品路线对照。统一 GF180 3.3V 库、corner、SDC 与约束；每组记录 cell area、寄存器数、宏数量/footprint、最高频率及关键路径。usbdev 缩 buffer 仅作为单独实验，包含 CSR/寄存器定义同步修改与回归。
4. **P0d：RAM/固件预算**：目标 CanoKey 固件在 RISC-V 交叉编译器下构建，报告 `.text/.rodata/.data/.bss`；在 QEMU/FPGA 用栈填充、水位统计及各功能组合测峰值 heap/stack，覆盖 CTAP/U2F、CTAP2 PIN/UV、凭据存储、OpenPGP/PIV/OATH 候选。不能只引用 STM32 64 KB 需求或 DESIGN.md 的“small RAM”描述。若还没可运行固件，记录为阻断，不填猜测值。
5. **P0e：USB 与熵**：先 FPGA/仿真跑枚举、重置、挂起恢复、错误包与 CTAPHID；用芯片实际 pad SPICE 模型，含封装/PCB/串阻，扫驱动强度、slew、负载、温度，按 USB FS 电气限值评审。环振只先做版图/网表振荡与熵采样试验；按预注册采样方法收集多芯片、多电压/温度样本，评估 90B min-entropy 与健康测试误报/漏报。无硅数据前不得将它标为可用安全熵源。
6. **P0f：存储/密钥验证**：从 SRAM/eFuse 编译器获取实际 LEF、时序、供电、编程接口文档；验证 OCD SRAM 端口、读写时序、保持/上电行为与 MBIST 策略；用 eFuse 测试芯片/公开硅数据确认编程电压、可用位数和断电原子性。PUF 仅测重复上电稳定性、温度/电压漂移和纠错辅助数据成本，不把 PUF 输出直接作为根密钥。
7. **P0g：物理实现**：按官方默认 pad/COB 首选配置跑完整 LibreLane：宏映射、pad ring、floorplan、PDN、CTS、routing、DRC/LVS、STA；统一报告 die/core/逻辑/macro/halo/拥塞面积。然后用 1×0.5 原生模板重复关键实验。短边自定义 pad、变窄电源环仅作隔离试验，不作为基准。

**GO（进入 P1）**：官方确认封装/引脚配置可用；USB 路线至少有合规 PHY 方案（片内 pad 通过电气审查或明确外置 PHY）；目标功能和信任边界冻结；RTL 闭包可综合；所需 SRAM/非易失存储有可采购/可验证实现；默认 pad 方案至少一项可复现物理实现达到可接受时序、无未解释 DRC/LVS/PDN 问题，并有项目批准的面积余量；固件 RAM/ROM 预算来自实际 build/测量。

**NO-GO / 转向条件**：普通 GF180 pad 电气不能满足 USB 且产品不接受外置 PHY；USB 48 MHz 时序在可用角落无法闭合；目标固件 RAM 或存储在 0.5×0.5 无解且 1×0.5/功能削减也不满足；无可接受的安全熵/根密钥/防回滚路径；或完整 PPA/物理实现无法通过。NO-GO 时只保留 FPGA/外置 PHY 原型或改为较大 slot/外置安全芯片，不能用估算面积或未经证实的安全属性豁免。

P0 的最终交付是一页决策记录：**所选 slot（0.5×0.5 默认或 1×0.5 备选）、pad/COB 版本、具体 CanoKey 功能、IP 版本与裁剪清单、USB PHY 方案、密码与熵源、密钥 NVM/回滚方案、ROM/RAM 实测、面积/STA/DRC/LVS 证据、GO/NO-GO 和未解决风险。**

## 13. 参考

- wafer.space 价格、slot 规格、Run 3 时间表：https://wafer.space/
- Run 3 众筹页：https://www.crowdsupply.com/wafer-space/gf180mcu-run-3
- eFuse 编译器：https://github.com/egorxe/gf180_efuse_compiler
- OCD SRAM：https://github.com/RTimothyEdwards/gf180mcu_ocd_ip_sram
- Foundry SRAM：https://github.com/google/globalfoundries-pdk-ip-gf180mcu_fd_ip_sram
- 7t 标准单元：https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu7t5v0
- IO 库：https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_io
- canokey-core（dev 分支）：https://github.com/canokeys/canokey-core
- canokey-stm32：https://github.com/canokeys/canokey-stm32
- canokey-crypto：https://github.com/canokeys/canokey-crypto
- Ibex 面积表：https://github.com/lowRISC/ibex/blob/master/README.md
- WebAuthn 签名计数器（双方为 0 时跳过检查）：https://github.com/w3c/webauthn/commit/92b5bfd7d7ac60402a163d67fc0d426843aad501
- 紧凑 ECDSA 引擎（11,366 GE）：https://www.researchgate.net/publication/303871700_Compact_ECDSA_engine_for_IoT_applications
- RFC 6979（确定性 ECDSA）：https://www.rfc-editor.org/rfc/rfc6979
- DFFRAM（sky130 密度对比表；gf180mcuD 尚不支持）：https://github.com/AUCOHL/DFFRAM
- OpenRAM（含 gf180mcu 工艺目录）：https://github.com/VLSIDA/OpenRAM

## 14. P0 实测补充：USB PE 验证（2026-11-15）

当前有效结论为本节后半部的 48 MHz TT/SS 预布局 STA 通过与最终映射面积；14.1–14.2 保留首轮历史背景。精简最终证据见 `p0/RESULTS.md`，原始时间戳报告和网表仅保留在本地忽略目录，可由复现脚本重新生成。

固定 OpenTitan `2e20836f9c9787bad82c84b5ba704223f06c8890`，GF180 7t5v0 Liberty
`43beb45e4d323a76239de436db2df6732e9a689b`。复现入口与边界见 `p0/README.md`。

### 14.1 基线修正与真实映射

原 wrapper 将 `link_active_i` 固定为 0，端点接口不可观察；此前 629 cells、
19,313.3696 µm² 的数字含功能常量裁剪，不能作为活动 USB PE 的预算。现 wrapper
完整暴露 2 IN/2 OUT、64-byte PE 边界，仿真和综合使用相同 top。
`p0/run-usb-fs.sh` 重新通过 Verilator lint、Yosys/slang generic 综合和 TT/SS 映射；
该历史轮次两角均为 **1,073 cells、33,961.9392 µm²（0.033962 mm²）**，244 个时序单元，
`check -assert` 零问题，无未映射/blackbox cell。
报告：`p0/reports/usb-fs-20261115T133323Z.txt`。runner 保留源/Liberty SHA256、工具版本及完整日志。

旧 undriven 警告属于未先导入 Liberty 驱动模型的检查流程错误，已由
`read_liberty -lib` 修复；本轮未修改上游 PE RTL。

### 14.2 已实际执行的数字协议验证

`p0/run-usb-sim.sh` 使用 Verilator assertions 和独立 C++ host NRZI/bit-stuff/CRC codec，
扫描 single-ended/differential 接收 × pin flip × 四个采样相位，共 16 组；每组 23 项检查通过。
最终报告：`p0/reports/usb-sim-20261115T133437Z.txt`。
覆盖 reset/link reset、IN NAK/STALL、地址/端点过滤、SOF/CRC5、OUT DATA0/ACK/toggle、
重复包 rollback、坏 CRC5/CRC16/PID/bitstuff、full NAK/STALL rollback、EP0 SETUP/DATA1、
IN payload/CRC16/ACK commit 与 missing-ACK timeout/retry、零长度和 64 字节 IN/OUT。

发现并核实 PE 接口契约：OUT strobe 包括尾部两字节 CRC16；地址达到 63 后饱和，
NAK 过程中也会停止递增。测试最初假设 payload-only 数据而失败，按上游 `usbdev_usbif`
的 CRC 处理修正了 scoreboard。未来端点包装需丢弃 CRC 尾并在 ACK 后提交，不能简单
按 PE 地址直接写 64-byte RAM，否则 CRC 会覆盖最后一个 payload 字节。探索失败日志保留。

当前仅证明上述定向数字行为；尚未覆盖枚举/描述符/CTAPHID、挂起恢复、isochronous、
时钟容差/jitter、完整畸形包空间、门级时序或 PHY/pad/PCB 电气。并非 USB/HID 认证，
亦不构成 P0 整体 GO。面积不含 PHY、HID/EP0、TL-UL/CSR、包 RAM、pad、封装、PDN、CTS/hold 修复与布线。

## 48 MHz pre-layout STA closure — 2026-11-15 14:58 UTC

Authoritative result: `p0/reports/sta-20261115T145829Z.txt`, exit **0**.
Mapping/lint: `p0/reports/usb-fs-20261115T145826Z.txt`; RTL regression:
`p0/reports/usb-sim-20261115T145829Z.txt` (368 checks / 16 configurations).
Exact sources, netlists, SDC and checker are archived with SHA256 manifests in
`sta-{corner}-20261115T145829Z-inputs/`. Earlier results are historical.

Unchanged budget: 20.833333 ns, setup/hold uncertainty 0.5/0.1 ns, I/O max/min
3.0/0.5 ns, transition 0.2 ns, output load 0.05 pF. Synchronous control/endpoint
ports remain constrained; usb_d_i/usb_dp_i/usb_dn_i remain asynchronous and
unconstrained. No timing cuts, false paths, multicycles or removed reset checks.

- TT: setup WNS **+7.2861 ns**, TNS **0 ns**, min slack **+0.2564 ns**;
  minimum recovery **+16.4347 ns**, removal **+1.0944 ns**.
- SS: setup WNS **+1.6943 ns**, TNS **0 ns**, min slack **+0.1489 ns**;
  minimum recovery **+15.2428 ns**, removal **+1.7222 ns**.
- Integrated baseline: TT +6.5481 / 0 / −0.1273 ns WNS/TNS/min;
  SS −1.3025 / −20.7696 / −0.5930 ns.
- Final mapped area including buffers: TT **1348 cells / 39853.8560 µm²**;
  SS **1348 cells / 42090.7648 µm²**, versus baseline 1344 cells and
  36528.1280/36993.5104 µm² (area +9.10%/+13.78%).

### Implementation

`run-usb-fs.sh` tightens ABC's target from 18000 to 12000 ps, retaining buf_4
input drive and 50 fF load. `buffer-reset.py` upgrades all 246 pin-compatible
GF180 dffrnq/dffsnq drive-1 flops to drive 4. ABC does not resize sequential
launch cells; this improves Q slew/fanout on RX endp_q → IN endpoint-index and
handshake cones without modifying upstream protocol RTL or adding latency.
Drive repair alone left SS WNS −0.4484 ns; tighter ABC mapping closed it.

Two rising-edge reset-release stages and asynchronous assertion remain. Internal
reset distribution retains 4 buf_8 roots / 31 buf_4 leaves for 244 RN/SETN sinks.
Four real GF180 buf_1 cells delay external rst_ni to both synchronizer RN pins.
External minimum arrival is now 1.7472 ns TT / 2.8924 ns SS, versus removal
required 0.6528/1.1702 ns. External recovery is +16.4347/+15.6206 ns; SS global
recovery minimum +15.2428 ns is internal. Global min slack is normal data hold.

This is valid **only under the existing 0.5–3 ns after-clock reset release
contract** and these two corners. A fixed delay cannot make arbitrary-phase
asynchronous release safe: it can shift a transition into a forbidden window.
Arbitrary-phase release qualification remains open if required; no first-stage
check is waived. Assertion acquires actual buffer delay; minimum reset pulse
width, fast corners, metastability, CTS/skew, routed RC and preservation of the
inserted cells need physical verification. Wait until the third rising edge
after compliant release before protocol traffic/writes. This is cell-delay
pre-layout closure, not extracted signoff, USB compliance or overall P0 GO.

### Verification

Lint, generic synthesis, GF180 TT/SS mapping, hierarchy/check assertions, all 368
RTL protocol checks, and complete two-corner STA pass. `test-sta-gate.py` now
exposes the three asynchronous USB pins required by the coverage checker and
verifies real pass=0 and actual reset-removal failure=1 at both corners.

`run-usb-gate-sim.sh` additionally runs the same 368 checks per corner on the
actual final mapped netlists using zero-delay Liberty functional models. Both
corners passed in `p0/reports/usb-gate-sim-20261115T150001Z.txt`; this is not
SDF timing simulation. Model import ignores missing functions on unused ICG
cells; actual instantiated cells are elaborated and functionally exercised.
Build warnings are retained in `p0/logs/gate-sim/`.

先按 `p0/README.md` 准备锁定依赖，再在 pinned Nix 中顺序复现：

```sh
./p0/run-usb-fs.sh
./p0/run-usb-sim.sh
./p0/run-usb-sta.sh
python3 p0/test-sta-gate.py
bash p0/run-usb-gate-sim.sh
```

Source/provenance hashes are checked; real timing failure remains exit 1 and
missing/tool/coverage failure exit 2. No commit or deployment was made.
