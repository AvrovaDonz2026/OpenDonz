# OpenTitan 密码子系统评估（2026-11-16）

## 决策与证据边界

用户优先级已记录：**P-256 以 OpenTitan 上游 OTBN 程序为主线；SHA/HMAC 以 OpenTitan IP 与官方驱动为主线。MbedTLS 只作独立参考及临时开发 backend。** 不以 quarter slot 预算或裸逻辑/触发器 RAM 展开预先否定 OTBN。不据本报告购买 slot；在完整配置、正确性、平台适配和布局时序证据补齐前不冻结最终架构。

已完成上游 P-256 向量执行、独立公钥/签名交叉验证、完整官方应用装配链接、RTL 依赖闭包导出、真实 GF180 宏容量映射和 HMAC 标准单元映射。OTBN 完整逻辑映射与含宏 Liberty 的预布局 STA 已完成；RTL 端到端周期、熵子系统与布线结果仍需分别说明；不能将条件估算当作硅上实测。

所有新增工程写入隔离 `crypto-hw/` 和本报告；没有改动 SoC/USB/PHY 公共文件，仅提交 crypto 评估范围的阶段成果，不 push。OpenTitan HEAD 实际核实为 `2e20836f9c9787bad82c84b5ba704223f06c8890`；其 git 状态只有未跟踪 `.DS_Store`，本评估未修改上游受跟踪源码。既有 P0 `ef14285` 与所有未提交工作保持。

## 可复核输入、闭包与许可证

- `crypto-hw/assess.py`、`otbn-measure.core`、`hmac-measure.core`：独立 FuseSoC 默认顶层导出；OTBN 274 个、HMAC 225 个导出文件（包含依赖/生成文件，不是只统计顶层 RTL）。`build/{otbn,hmac}/inputs.json` 记录各文件 SHA256、导出命令、库哈希。顶层包括 TL-UL、寄存器、alerts、primitive；EDN/OTP/keymgr/KMAC 是暴露的外部接口，并未因为包依赖而被当作已集成模块。
- `crypto-hw/evidence/upstream-software-sha256.json`：766 个 OTBN 密码程序、工具、ISA 模拟器、测试、官方 ECC/SHA2/驱动及根 LICENSE 文件的哈希。RTL 闭包逐文件 SPDX/notice 扫描另存 `evidence/rtl-license-inventory.json`（生成文件可能没有独立声明，需追溯生成器）；源码保留上游版权/许可证标识；根 OpenTitan Apache-2.0 许可证另存 `OPENTITAN-LICENSE`。闭包可能含 vendored 文件，应保留各文件原有 notices；本报告不把根许可证当作替代逐文件声明。
- GF180 标准单元：`p0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.combined.lib`，SHA256 `c4a64618856caa93b31755d8e22acb7e7efdaaaa3b06cac4a72e3abbf17f861c`，TT/25°C/3.3 V。Yosys 0.69 + Slang；HMAC 映射日志记录具体构建版本。
- OCD SRAM：`gf180mcu_ocd_ip_sram__sram1024x8m8wm1`，固定提交 `d41c7447d34d0c298158094378c8268560941724`，Apache-2.0；LEF、TT Liberty、功能/时序 Verilog、黑盒、引脚说明及 LICENSE 在 `crypto-hw/evidence/sram/`，逐文件哈希在 `manifest.json`。这是一种可评估的公开宏选项，不等于代工/提交平台已承诺接受此宏；GDS/DRC/LVS/平台许可需另行确认。
- 本地适配和证据哈希见 `evidence/assessment-local-sha256.json`。导出清单描述导出文件，宏替换由 `assess.py --macros` 与本地适配哈希共同界定。

工具可复现限制：隔离 `.venv` 安装 FuseSoC、PyYAML、pyelftools、semantic_version、pycryptodome 等；本地 FuseSoC schema 将空文件列表 `minItems` 从 1 放宽至 0（上游存在空 waiver fileset），未改 OpenTitan。OTBN 汇编使用 Homebrew GNU RISC-V assembler/linker，由上游 Python 工具封装；显式 `-march=rv32i_zicsr` 允许 CSR 指令。Slang 单编译单元需本地 `prelude.sv` 导入 assertion/flop 宏。完整环境不是免安装交付物。

## 上游 P-256 真实执行

脚本 `crypto-hw/vectors.py` 直接装配未改上游 `sw/otbn/crypto/tests/*.s`，用上游 `.exp` 比较寄存器，再由 `otbnsim/standalone.py` 转储 DMEM、寄存器和 stats。以下均 PASS：

- `p256_base_mult_test`：573,718 条指令，595,532 个 ISA 模型周期，21,814 stall；ELF text/data/bss = 3,192 / 416 / 452 字节。
- `p256_key_from_seed_test`：82 条指令，107 个 ISA 模型周期，25 stall；text/data/bss = 3,208 / 352 / 452 字节。这里只检查种子到标量过程，**不是完整随机密钥对生成延迟**。
- `p256_ecdsa_sign_test`：606,993 条指令，630,404 个 ISA 模型周期，23,411 stall；text/data/bss = 3,996 / 576 / 832 字节。
- `p256_ecdsa_verify_test`：402,281 条指令，421,107 个 ISA 模型周期，18,826 stall；text/data/bss = 4,076 / 416 / 704 字节。

以上周期来源是 **Python ISA 模型（含它建模的 pipeline stalls），不是 Verilator RTL 周期，更不是硅上测量**。模型提供的随机数不证明 GF180 上的真熵质量或 EDN 吞吐；未包含主 CPU MMIO 装载、总线争用、平台随机源等待和完整启动/清零成本。按尚未闭合的 24 MHz 纯算术换算，基点乘 24.814 ms、签名 26.267 ms、验签 17.546 ms；不能据此承诺实机延迟。100 MHz 的模型打印只是频率换算，不是 GF180 目标频率证据。

`independent_check.py` 从 DMEM 还原两份私钥 share 的模 n 和，从 OTBN 输出取 affine x/y、r/s，并以 Python cryptography/OpenSSL SECP256R1 检查：公钥一致 PASS、ECDSA 预哈希签名 PASS、篡改摘要被拒绝。证据 `build/vectors/independent.json`。这些是独立正确性交叉验证，不代替 NIST/CAVP、完整恶意输入覆盖或侧信道/故障认证。

还完整装配链接官方 `run_p256`（包括 base/b2a/isoncurve/check/proj/a2b/shared_key/sign/verify）：text 6,260、data 352、bss 1,760 字节，`build/vectors/run_p256-build.json`。默认基线阶段官方完整入口只完成构建；后续 8 KiB 隔离配置的入口执行结果见增补。不能把 ISA 入口执行称为“官方 C API 端到端已运行”。小向量 ELF 占用也不能作为缩小默认 OTBN 内存的已验证理由。

RTL 执行尝试：上游 `otbn_top_sim` FuseSoC/Verilator 导出被 `prim_asap7` 缺失 `lint/prim_generic_clock_mux2.vlt` 阻塞。尚无端到端 RTL 运算周期；需要隔离顶层技术映射配置修复后运行，不回写共享 SoC 工程。

## OTBN 完整内存与 GF180 宏适配

以当前固定 RTL 默认配置为准（不是早期 OpenTitan 文档的小容量）：`otbn_reg_pkg::OTBN_IMEM_SIZE = 0x4000`，`OTBN_DMEM_SIZE = 0x4000`；`otbn_pkg::DmemScratchSizeByte = 16384`。

- IMEM：16 KiB 逻辑数据，4,096 × 32 位；每词 SECDED 后 **4,096 × 39 位** = 159,744 存储位。
- DMEM：16 KiB 总线窗口 **加 16 KiB 内部 scratch**，32 KiB 数据，1,024 × 256 位；8 组 32→39 位完整性编码后 **1,024 × 312 位** = 319,488 存储位。
- ECC 存储总量 479,232 位（58.5 KiB）；宏字节宽对齐后分配 59 × 8,192 = 483,328 位（59 KiB）。不要只数总线窗口 16 KiB，不要将 DMEM 312 位当 256 位，也不要重复增加一个不存在的完整 DMEM 副本。
- 默认 `RegFileFF` 与硬化控制/数据通路在逻辑综合中保留；这不代表 IMEM/DMEM 用 FF 展开。`Stub=0`、`FeatStubMai=0`，未为保面积关闭 masking accelerator。SRAM scrambling、ECC 编解码、读端口仲裁、TL-UL 访问、清零/告警等逻辑亦在 OTBN 顶层闭包。

LEF 实际尺寸 301.300 × 515.810 µm，每宏 0.155413553 mm²：

- IMEM：深度分 4 banks，每 bank 39 位向上取整为 5 个 8 位 lanes，共 **20 宏 = 3.108271060 mm²**。
- DMEM：1 bank × 39 lanes，共 **39 宏 = 6.061128567 mm²**。
- OTBN 内存本体共 **59 宏 = 9.169399627 mm²**，不含 halo、通道、布线、标准单元和外围平台。它是所选默认配置和宏的确定成本，不是所有 OTBN 实现的最小面积证明。

适配 `crypto-hw/rtl/prim_ram_1p.sv` 保持单端口同步读取，CEN/GWEN/WEN 极性映射，捕获 read bank，bank 输出选择，宽度补零，按位写掩码映射。OTBN 看到的是原逻辑容量/数据宽度，没有把 scratch 去掉；未实现冗余修复或 memory configuration 的实际工艺控制，cfg response 返回默认值，需平台审核这些接口是否可安全固定。

`rtl/macro_tb.sv` 使用固定的宏 Verilog，真实 IMEM 4 banks × 39 位与 DMEM 1 bank × 312 位配置分别测试同步读、最高有效位、掩码写和原位保留 PASS；IMEM 另测倒序跨 bank 读取和不串写。日志 `build/macro-test.log`、`build/dmem-test.log`。修正测试 bench 时间单位并在每 bank 先做 read enable 初始化后通过；宏模型要求 CEN 1→0 初始化，其初次写前行为不能忽略。当前 PASS 不是全地址覆盖、reset/wipe/ECC 故障注入、完整 OTBN RTL 验证或门级 SDF 验证。生产适配仍需确认上电/CEN 协议，不能凭 bench 初始化推定 SoC 已满足。

宏 TT Liberty 已收集；源 Verilog nominal 3.3 V 标称周期 9.241 ns、CLK→Q 6.215 ns，但仅是宏局部模型规格，不能作为带 bank mux、scrambler/ECC/控制路径的 OTBN 频率。模型注释还指出部分 CSV corner 数据疑似抄写问题；本评估未更改宏模型或据此认证工艺时序。需宏 Liberty + logic + clocks + corner + 布线 STA，setup/hold/最小脉宽/电源条件一起检查。

OTBN 首轮映射检查失败：Slang 将不带黑盒属性的空宏声明展开为无驱动输出（472 warnings），得到的 4.196781 mm² **无效，禁止用于判断 fit**。日志保存在 `build/otbn/invalid-no-blackbox.log`。已添加 `--empty-blackboxes` 并断言 elaboration 后恰有 59 个宏，重跑成功。最终网表保留 **59 宏 + 154,622 标准单元**（合计 154,681 实例）；标准单元 **4,280,839.763199 µm² = 4.280839763199 mm²**，其中时序单元 1.432736794 mm²。Yosys 的面积明确不含宏（报告 unknown），应另加 LEF 宏面积：**OTBN 本体合计 13.450239390 mm²**。`build/otbn/gf180.log` 和 `map.ys` 是源证据。不能将宏容量乘上 FF 单元面积代替硬宏成本。

`build/otbn/timing.tcl` / `timing.log` 已实际运行 OpenSTA，读入标准单元和 SRAM TT Liberty。core 最小周期 **303.81 ns**（约 **3.29 MHz**），24 MHz setup slack **−262.15 ns**，该初始综合网表不闭合。三个时钟暂设同周期、理想时钟、无寄生、未 buffer/resize；IO delay 是诊断约束，尚未形成实际 CDC/reset/false-path/multicycle 集成约束，未做多角/hold/布线签核。EDN/OTP 单域的短周期报告不能用作 OTBN 运算频率。该结果不证明物理优化无法提高频率。

## HMAC/SHA-2 顶层 GF180 实测

顶层 `hmac` 完整保留 SHA-256/384/512、多种 HMAC key 长度、寄存器/TL-UL、keymgr sideload 接口、alerts、interrupts、packer 与 32 项 FIFO（数据之外还有 byte mask）。未只测裸 SHA 轮函数。

`build/hmac/gf180.log`：36,109 个映射单元，标准单元面积 **931,858.009600 µm² = 0.9318580096 mm²**；其中时序单元 353,515.008 µm²（37.94%）。这包含 IP 内接口逻辑，不包含外部 TL 主机桥、alert handler、keymgr、安全熵平台或主 CPU/USB/通用 RAM。

`build/hmac/timing.tcl` / `timing.log`：OpenSTA，41.6667 ns 时钟，输入/输出 delay 2 ns，理想时钟、未布局/未做物理优化的综合网表。最差路径到达 **382.81 ns**，报告最小周期 **385.09 ns**（网表推导约 2.60 MHz），24 MHz 约 -341.69 ns slack，**失败**。该数据说明这个映射网表没有闭合 24 MHz，不是布线后的认证最高频率，也不能证明优化无法达到目标。后续需负载/转换约束、buffer/resize、物理综合与真实时钟树；多角验证。

尚未实际执行 HMAC MMIO 驱动/KAT，未获得这个配置的 RTL 端到端 SHA/HMAC 消息周期，因此不报告虚构的吞吐。必须加入官方 SHA-256/HMAC 向量、非整字节消息、不同 key 长度、FIFO 背压、context/错误/清零路径，再由 RTL/平台测量。

## 官方软件复用与平台依赖

已查证当前固定源码：

- `sw/device/lib/crypto/impl/ecc/p256.c`：`p256_init_otbn()` 装载 `run_p256`，之后 DMEM 写入/执行/回读；它是官方 OTBN 包装/驱动路径，**不是完整便携 C 曲线算术实现**。依赖 OTBN 驱动、keymgr_dpe、hardened/status/integrity，以及 `top_earlgrey` 生成地址等。
- `sw/device/lib/crypto/impl/sha2/sha256.c`：使用 OTBN 的 `run_sha256`、masked state/message shares，并依赖 `rv_core_ibex` 等；不能将文件名为 sha256.c 等同于纯软件 fallback。
- `sw/device/lib/crypto/drivers/hmac.c`：硬件 MMIO、生成寄存器、固定 top 地址、hardened 基础设施；适合作为 HMAC IP 官方驱动移植主线，需要改平台地址/时钟/中断/错误处理并验证编译器与 hardened primitive。
- 复用工具、数据结构、字节序转换、状态/错误处理与官方汇编是可行工作；“免移植的 OT 软件 P-256”并无证据。没有因硬件受阻擅自更换为其他密码实现。

必须补齐：主 CPU 总线到 TL-UL 请求/响应与 integrity 处理；寄存器与内存窗口地址；中断/alerts/escalation 处理；OTBN EDN 的 RND/URND 两路请求响应/CDC；OTP scrambling key/nonce 更新；keymgr sideload 禁用或实现的安全语义；KMAC 应用接口的真实使用/合法 idle 回应；reset 顺序、错误锁定与安全 wipe。包结构可编译不等于这些服务已实现。

GF180 熵路径尤其未闭环：物理噪声源需采样/偏置/温压/老化证据、启动与连续健康检测、失败关闭策略，再对接已评估的 conditioner/CSRNG/EDN。不能将固定种子、ISA 模拟随机数或单个无校准 ring oscillator 当合格熵源。若复用 OpenTitan ENTROPY_SRC/CSRNG/EDN，需完整依赖、面积/时序/固件初始化重新测量；目前未计入成本。非生产开发可用明确标识的外供随机数测试接口，不能据此声称安全产品完成。

## Slot 与完整组合的条件建议

仓库模板 core 面积：quarter 1.732644 mm²；0.5×1 4.458376 mm²；1×0.5 5.020056 mm²；1×1 12.917424 mm²。这是几何上界，不是所有面积均可用作标准单元。

所选上游默认 OTBN 内存 9.169400 mm² 已单独超过前三种 core。此结论来自真实宏，不来自 FF 展开，也不宣称换宏/改配置一定不可能。**有效映射后，默认 OTBN 本体 13.450239 mm² 已超过 1×1 core 12.917424 mm² 约 0.532815 mm²（4.12%）**；加 HMAC 后为 **14.382097400 mm²**，超过约 1.464673 mm²（11.34%），还未计 CPU/USB、平台熵、通用 RAM、halo、时钟和路由。因此所测默认配置不能放入这些模板。结论限于当前宏、默认配置和实际映射；继续优先评估 OpenTitan 的更大可用 core 或独立验证配置，不能由此宣称全部 OTBN 实现不可能。

优先保留 OpenTitan 能力继续测完整 OTBN/HMAC/平台组合，并评估更大可用 core/多宏布局。若要缩小 IMEM/DMEM 或关掉功能，应成为单独、可追溯配置：官方完整 `run_p256` 6,260 字节 text 已超过 4 KiB；栈/scratch/未来应用/wipe/寻址假设需重新核查、重新生成寄存器窗口并重新跑正确性/安全路径。程序静态占用不是硬件 scratch 最小值证明。

目前没有完整、可比的 CPU+OpenTitan 硬件方案与 CPU+软件方案 GF180 总成本/时序，所以不宣布某成熟替代核或软件必胜。既有固件的 14 边界向量、RFC 公钥、独立签名、熵失败等由 SoC 负责人持有，可作参考 backend 的证据；本任务未重跑，不将其冒充 OTBN 或本次硬件验证。只有完整配置正确性、测量与平台适配给出明确阻塞时，再提出具体成熟实现 fallback，并同样测量全组合。

## 冻结前验收缺口

1. 已完成 OTBN 59 宏保留映射与含宏 Liberty 的初步 STA；需要物理优化、完整时钟/CDC 约束、布局和多角结果，重新选择能承载默认配置的面积候选。
2. 修复隔离 OTBN RTL target，实际跑公钥、签名、验签，分别量装载、执行、清零、随机源等待与总线成本；不能用 ISA 周期代替。
3. HMAC 官方驱动适配与 RTL KAT/边界测试，明确 24 MHz 失败路径的优化结果。
4. 确认宏交付/平台接纳/GDS/DRC/LVS与电源时序，扩大 DMEM/上电初始化/掩码/ECC/安全 wipe 适配测试。
5. 选定并实测 GF180 合格熵、CSRNG/EDN、OTP/keymgr/alert/生命周期服务，以及主 CPU/USB/通用存储全组合。

本次保持 OpenTitan 首选决策，架构仍处评估状态；以上缺口显式阻塞冻结，不构成对 OpenTitan 能力的预先否决。


## 8 KiB IMEM 隔离配置增补（2026-11-16）

本轮只缩 IMEM，保留 16 KiB 总线 DMEM + 16 KiB private scratch、39/312 位 ECC 存储、scrambling、安全擦除、RND/URND 与重播种相关 RTL。`configure.py` 从固定提交复制 OTBN 到 `build/imem8`，修改 HJSON 的 IMEM items 4096→2048，再用上游 reggen 重新生成寄存器包、寄存器顶层和 C 头。汇编工具、内存视图、链接模板均来自该隔离树，链接器通过上游 mem_layout 读取新 HJSON；默认上游与 16 KiB 基线保持不变。修改闭包及哈希见 `evidence/results/imem8-configuration.json`；综合实际输入哈希见 `build/otbn8/effective-inputs.json`。

新组织为 IMEM 2048×39：2 banks×5 lanes = 10 宏；DMEM 仍 1024×312：39 宏。共 49 个 1024×8 宏，宏面积 **7.615264097 mm²**，相对基线 59 宏减少 **1.554135530 mm²**。这只是确定的宏面积差，标准单元必须使用本次有效映射结果，不能沿用基线值。

链接/ISA 边界检查 PASS：8192 字节 text 可链接、8196 字节溢出被拒；跳到 8192 触发 BAD_INSN_ADDR=2；非法 DMEM 地址 ERR_BITS=1；非法指令 ERR_BITS=8。完整入口 text/data/bss = 6260/352/1760 B，private `.scratchpad` 为 0x4000 起的 256 B，未重定位。ISA 使用上游 StandaloneSim 合成随机数且跳过启动擦除，不能证明 RTL ECC/扰码/wipe/熵安全；局部 SRAM 宏测试亦不覆盖这些整核安全路径。

RTL 层已通过 SHA-256 原语 abc KAT 与 digest 零清除；IMEM 2048×39 和 DMEM 1024×312 实际宏模型同步读、bank 选择、掩码写/不串写测试通过。宏模型首次 CEN 初始化警告及 bench 的 read priming 保留在日志，平台上电协议尚需验证。官方 `dif_hmac.c` 真实编译、start/push/process/finish 与错误参数 MMIO 合约通过；host-only dt 类型与寄存器数组是测试适配，不是硬件 HMAC KAT。尚未完成 HMAC 顶层加密 KAT、FIFO 背压及总线端到端测试。

隔离 OTBN top RTL target 原技术依赖问题经 generic primitive 依赖调整后，现阻塞于上游工具要求 **Verilator >=5.048**，本机为 **5.046**。不绕过版本门槛冒充完整 RTL 已通过。最小后续条件是受支持工具链，再运行完整 top + 官方程序 + 外部服务行为模型；物理熵仍需单独资格验证。

### DMEM 实际替代宏核查

固定 OCD SRAM 提交中 512×8 宏已缓存 LEF、TT Liberty、功能 Verilog、blackbox 与哈希：`evidence/sram-alternatives/manifest.json`。LEF 实际为 **301.300×321.890 µm = 0.096985457 mm²**（以文件实值为准）。其单端口/按位写掩码组织可供后续适配验证，但没有获得目标流片平台接纳/GDS/DRC/LVS 的确认，不能称为已可流片。

保持当前 32 KiB DMEM 与 312 位单周期接口，512×8 需要 2 banks×39 = 78 宏，面积 **7.564865646 mm²**，比当前 39 个 1024×8 的 **6.061128567 mm²** 更大。因此本轮继续使用已经测试的 1024×8 DMEM 组织。若将总 DMEM 减半到 512×312，39 个 512×8 可降到 **3.782432823 mm²**，但须改变总线窗口/私有 scratch 划分、重定位 0x4000 scratch 并验证全部入口、地址隔离和 wipe；当前未实施，不把这个候选当成已验证方案。只截短深度而仍选 1024×8，39 条 byte lane 仍不可少，不产生宏数节省。


### 8 KiB 有效映射与同条件 STA 结果

实际完成新配置完整 GF180 技术映射，最终网表 **49 宏 + 154,030 标准单元 = 154,079 实例**；对最终 `mapped.v` 独立运行 Yosys `select -assert-count 49`。标准单元 **4,268,281.023999 µm² = 4.268281024 mm²**（其中时序单元 1.431314304 mm²），加 LEF 宏 7.615264097 mm²，**OTBN 本体共 11.883545121 mm²**。相对默认 13.450239390 mm²减少 **1.566694269 mm² / 11.65%**；这是本次网表实测，非旧逻辑面积复用。加入已测 HMAC 后 **12.815403130 mm²**。

同 TT 库、相同三个理想时钟和诊断 IO 约束，OpenSTA 读取宏 Liberty 得到 core 最小周期 **306.48 ns / 3.26 MHz**，24 MHz setup slack **−264.81 ns**，仍失败。与基线 303.81 ns 相比未改善；EDN/OTP 局部短周期不代表 core 运算速度。无布线寄生、真实 CDC/reset/multicycle 或多角/hold 签核，不能承诺最高频率。

1×1 几何 core 12.917424 mm²与 OTBN+HMAC 只剩 **0.102020870 mm²**，尚缺 CPU/USB、合格熵、平台服务、通用存储、halo、通道和利用率，因此不能以该纯面积和宣称完整 SoC 放得下；其他较小 slot 仍容纳不了本次测量组合。架构不冻结。可复核源日志、输入清单、网表哈希和汇总已从 ignored build 复制到 `crypto-hw/evidence/results/imem8-*`。


### 完整官方 P-256 入口执行结论

`full_p256.py` 已在 8 KiB 内存视图中实际执行全部 **11 种官方 mode**，另含篡改摘要和非法 mode，共 **13 个 case PASS**。基点乘 595,790、签名 630,738、验签 418,579、随机 keygen 595,969、sideload keygen 595,846、sideload sign 630,803、sideload ECDH 611,127、普通 ECDH 611,060、on-curve 484、算术分享 399、固定 k 签名 630,583 个 **ISA 模型周期**；非法 mode ERR_BITS=8，篡改摘要不匹配恢复 r。来源 `evidence/results/p256-imem8.json` 含 ELF 哈希、section 容量和逐项结果。

公钥/随机 keygen、普通/固定 k/sideload 签名、普通 ECDH 与分享结果有 Python cryptography 或明确数学关系独立交叉检查；sideload keygen 公钥用于独立验证 sideload signature。sideload ECDH 本次只检查正常结束/ERR_BITS=0，尚无独立共享点 oracle，不把它与完整向量认证等同。sideload 附加 seed 是上游定义的 64 B，测试最初只初始化 32 B 导致模型 DMEM integrity 错误；按上游两次 32 B 读取修正后全部执行通过，未降低模型完整性检查。

仍待完成：受支持 Verilator 的完整 OTBN RTL/官方入口、reset/secure wipe/ECC 故障注入与隔离验证；HMAC 顶层官方 KAT；实际平台认可的 SRAM 交付与物理优化/多角签核；合格熵及 EDN/OTP/keymgr 等平台服务。以上不因局部 PASS 而消失。


## 8 KiB IMEM + 16 KiB 总 DMEM 评估增补（2026-11-16）

本节更新前述“尚未实施”的 DMEM 候选状态。隔离配置 `build/imem8-dmem16` 将 HJSON CPU DMEM 窗口降到 2048×32 位，同时将 `otbn_pkg.sv` 私有容量常量和软件 `mem_layout.py` 常量改为 8192 B；reggen 重新生成寄存器顶层、寄存器包和 C 头。CPU 内部可见地址为 0x0000–0x1fff，内部私有 scratch 为 0x2000–0x3fff，总逻辑容量 16 KiB，ECC 实际组织为 512×312 位。TL-UL 主机窗口仍从 0x8000 开始，末地址 0x9fff。IMEM 从 0x4000 开始、8 KiB。默认与上一轮独立目录不变。

官方链接模板从 CPU 窗口大小计算 `.scratchpad` 原点，无需修改官方 P-256 汇编：text/data/bss 为 6260/352/1760 B，256 B scratch 从 0x4000 移至 0x2000。完整十一 mode 加篡改摘要、非法 mode 共十三 ISA case 全通过，周期与上一轮相同；独立 cryptography 算术/签名交叉检查保留。8 KiB public data 可链接，8196 B 被拒；IMEM 8192/8196 B 边界与取指越界通过；DMEM 总容量外 0x4000 读取触发 BAD_DATA_ADDR=1，非法指令 ERR_BITS=8。此层使用上游合成随机数和跳过启动擦除的 ISA harness，不能作为硬件擦除或熵安全结论。

宏组织变为 10 个 1024×8 IMEM + 39 个 512×8 DMEM，共 49 宏。512×8 实际 LEF 面积 96985.457 µm²；宏面积合计 5.336568353 mm²，比上一轮 7.615264097 mm² 减少 2.278695744 mm²。39 byte lanes 无法随深度缩短而减少；必须使用较浅宏才能取得这项面积差。实际模型通过 512×312、1024×312、2048×39 同步读、掩码写、最高位/最高地址和 bank 不串写测试。LEF/TT Liberty/Verilog 已固定，但平台接纳、GDS、DRC/LVS 与物理供电/时序资格仍未确认。

已解除 Verilator 工具版本阻塞：本地固定 v5.048 源码、autoconf 与已安装 Flex 2.6.4 构建，无全局安装。macOS 系统旧 Flex 首次生成 lexer 导致链接缺符号，使用现代 Flex 重新生成后成功。`build_verilator.py` 保存源码归档哈希及工具版本。

完整 `otbn.sv` generic RAM 功能仿真已运行真实 TL-UL 装载和输出读回，保留 ECC/扰码/启动内部安全擦除/每次执行重播种。私有区首尾内部 store/load、host 越窗 read/write 拒绝、DMEM 显式擦除换钥、官方基点乘输出、签名、验签输出及非法 mode 通过；实际 RTL 签名从 CSR 窗口读出后由 cryptography/OpenSSL 独立验签。外部 EDN/OTP 是明确标识的确定性功能服务模型，不能证明真实随机性、种子资格、重播种抗攻击能力。DMEM 命令擦除采用上游全阵列换钥机制，未宣称物理逐字清零；启动和执行结束内部 wipe 也不能与清除整个 scratch 内容混为一谈。ECC 故障注入、擦除故障/生命周期锁定/RMA、真实多时钟 CDC、侧信道及物理 remanence 仍未证明。

HMAC 顶层 KAT 已通过真实 TL-UL 命令与数据完整性、CSR 配置、FIFO 写与 digest 读回：SHA-256 空串、abc，以及 RFC4231 HMAC-SHA256 “Hi There”。这替代了此前只有原语 KAT/模拟 MMIO 的缺口；尚不覆盖全部 SHA 宽度、长报文压力、FIFO 背压及所有异常组合。


本轮 GF180 最终映射：**10 个 1024×8 + 39 个 512×8**，**154,957 标准单元 + 49 宏 = 155,006 实例**，标准单元面积 **4.267047322 mm²**（时序单元 1.431176006 mm²）；加宏面积 **5.336568353 mm²**，OTBN 本体 **9.603615675 mm²**。加已测 HMAC 为 **10.535473685 mm²**，相对上一轮 OTBN+HMAC 12.815403130 mm² 减少 **2.279929445 mm²**。这些是综合网表逻辑与 LEF 宏面积之和；尚未计 CPU/USB、合格熵、平台服务、halo、路由、时钟树及布局利用率，不代表 1×1 slot 的完整 SoC 可交付。

相同 TT 库与诊断约束，含两种宏 Liberty 的 OpenSTA core 最小周期 **301.74 ns / 3.31 MHz**；24 MHz setup slack **−260.08 ns**，仍失败。三个理想时钟、2 ns IO delay、无布线寄生且未完成物理优化/多角/hold/CDC 签核，不能把该周期当真实流片最高频率。

实际 foundry SRAM 模型直接接零延迟同步 RTL 时，整核首次有效读回出现 ECC/data 不一致：模型在 CLK 后 100 ps 使用 live write/control 输入，而同步 RTL 已在同沿更新下一拍信号。另行提供 **仅用于仿真的** `prim_ram_1p_model_hold.sv`，输入 transport delay 200 ps，为模型提供 hold 区间；综合及局部宏 bench 仍使用无延迟 `prim_ram_1p.sv`。此分层必须保留：带模型 hold 的整核功能仿真不能证明真实 silicon hold closure，更不能替代门级 SDF/STA。没有修改上游宏模型，也没有关闭 ECC、TL 完整性或跳过 wipe。


带上述明确 hold 假设的实际 SRAM 模型整核运行最终 **PASS**：startup wipe、EDN handshake/reseed、host 越窗读写拒绝、private scratch 首尾、DMEM 换钥、base_mult/sign/verify/invalid_mode；签名读回由 cryptography/OpenSSL 独立验签。generic 与 macro 两层的输出日志分别封存为 `evidence/results/otbn-full-generic.log` / `otbn-full-macros.log`；全部十三 ISA case 与边界最终复跑通过。十一 mode 的覆盖仅在 ISA 层；完整 RTL 只覆盖上述关键路径，不把二者合并宣称十一 mode 全部 RTL 通过。ReadLints、项目脚本语法与 diff whitespace 检查通过。
