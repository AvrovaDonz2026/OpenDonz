# Checkpoint 1 — RV32 U2F 构建、资源实测与 GF180 容量筛查

日期：2026-11-16。基线 `ef14285`。本阶段范围为 SoC/firmware，未修改 P0、USB analog 或 PHY 评估文件；Git 提交状态以仓库历史为准。

## 结论及验收边界

已交付固定版本的开源 U2F APDU/HID、软件 SHA-256/HMAC/P-256 的 RV32IMC/ilp32 ELF，
可重复编译与函数级 RV32 指令执行、真实 map/size/编译器栈帧报告，以及 GF180 标准单元映射。
**这不是完整可工作的 U2F SoC，Checkpoint 1 的端到端功能验收仍未通过。**
实际 Ibex 复位至 mailbox INIT/VERSION 已通过；USB PE/EP0 桥的下述数字线级集成测试已通过。
真实熵、持久 NVM、调试互连及物理存储宏尚未完成。
注册/认证逻辑已编入，尚未做真实主机的注册/认证；attestation 故意保持未配置。

首版范围仅 U2F USB HID、注册/认证、实体按键及设备密钥持久保存。
没有加入 CTAP2、OpenPGP、PIV 或专用 P-256 硬件引擎。
持久保存目前只有明确的软件接口契约，不能称作已实现的持久密钥保护。

## 密码实现优先级（最新用户路线）

**优先采用 OpenTitan OTBN P-256 与 OT HMAC；生产密码架构尚未冻结。**
独立负责人 `200b4791-1807-4007-84fd-d79fd2754e16` 拥有 `crypto-hw/` 与
`docs/opentitan-crypto-assessment.md`，本任务不重复调查，也不修改其文件。
待其接口与依赖验证结果后再接入；本次没有伪造 OT 驱动或以 stub 宣称已接入。
保留 `ecc_compute_public_p256r1` / `ecdsa_sign_p256r1` 可替换接口，后续 HMAC/SHA
亦需面向 OT HMAC 契约适配。Mbed TLS 3.6.5 仅是已通过功能 qualification 的参考模型与
临时开发 backend，其 ROM/RAM/执行数据不能代表最终 OT 组合。
最终安全和性能结论必须针对选定实际软硬件组合重新验证；不为 quarter slot 放弃 OT 能力，
也不依据 generic SRAM 尚未宏适配时的触发器面积否决 OpenTitan。

## 固件来源与构建结果

来源、固定 commit、许可证及复现命令见 `firmware/README.md`。
U2F-TOKEN `2c19a75c31096e19cbcfcedeae6bb18077eabac0` 的现有 STM32/Tomu 支持有上游记录；
移植其 APDU/HID/SHA/HMAC；P-256 使用 Mbed TLS 3.6.5，commit
`e185d7fd85499c8ce5ca2a54f5cf8fe7dbe3f8df`（Apache-2.0 或 GPL-2.0-or-later）。
GPL-3.0-or-later / Gladman 条件 / BSD-2-Clause 均保留上游许可信息。
未把“已有部署”解释为当前 RV32 移植的密码认证或安全审计结论。

Clang 23.1.3（见当前 inputs.json 的 compiler 记录），`--target=riscv32-unknown-elf -march=rv32imc -mabi=ilp32 -Oz`，
freestanding，`-Wall -Wextra -Werror -fstack-usage`。无系统 heap；Mbed TLS 在静态 8 KiB arena 内部动态分配并在调用后清零。
启动入口位于 0x80，初始化 data/bss，栈顶 0x10004000；ROM 链接上限 128 KiB，
RAM 16 KiB，NVM 4 KiB。**链接上限不是实际物理存储器。**

实测 `firmware/build/u2f.elf`，map 在同目录 `u2f.map`：

- `.text`（含 rodata）24,084 B，`.data` 12 B，加载用 ROM 内容共 24,096 B；另有入口偏移和对齐。
- `.bss` 9,748 B，静态 RAM 总计 9,760 B；不含运行栈、未来 USB 控制器缓冲与中断上下文。
- `.device.key` / `.auth.ctr` / `.attestation.cert` 各 1,024 B，NVM 共 3,072 B。
  这些区域不能当 ROM 常量、也不能省略掉当作已保护根密钥。
- 编译器栈帧：APDU dispatcher 464 B；HID loop 64 B；ECC 公钥入口 224 B、签名入口 208 B，ecp_mul_restartable_internal 256 B；SHA process 160 B。
  全部 Mbed TLS 逐函数帧见 `stack.json` 与 `.su`。

不能对这些帧取最大值就称作峰值，也不能把互斥调用全部相加当准确值。
存在曲线函数指针和编译器 outline helper，尚无完整可证明的静态调用链上界。
链接器保留 4 KiB 栈；这是预算，不是经过最坏路径证明的需求。

## 实际执行验证及限制

`firmware/test_rv32.py` 使用 Unicorn 2.1.4 执行真实 RV32 ELF 指令，
RAM 映射 16 KiB，栈顶与链接脚本一致，使用 Python cryptography 的 NIST P-256 交叉验证。

- 标量 2 的公钥与参考一致；P-256 签名被独立参考库验证通过。
- `U2F_VERSION` 返回 `U2F_V2 9000`。
- 三条路径的**写入栈水位下界**分别为 696 B（公钥）、792 B（签名）、40 B（VERSION）。
  栈预填 0xa5，扫描实际改写字节；未写的栈槽和恰好为 0xa5 的写入可能漏计。
  VERSION 的写水位 40 B 不否定 dispatcher 的静态 464 B 帧。
- P-256 边界资格 **PASS**，证据见 `firmware/evidence/crypto-edge.json`，复现入口
  `python3 firmware/test_crypto_edges.py`。0、n 拒绝；1、2、n−2、n−1 与八个派生标量共 14 例
  通过；RFC 6979 公钥向量、原生/RV32 签名一致性及独立签名验证通过，四种熵失败均拒绝。
- 保留适配层成功/失败契约与声明检查；RFC 6979 精确 nonce/r/s 向量通过 test-time RNG wrap 验证。
- 历史 micro-ecc exceptional-point FAIL 在 `firmware/evidence/history/micro-ecc/` 保留；
  当前参考后端已由成熟 Mbed TLS 替代，未修改密码算法或特判 scalar 边界。
  本次保留既有 qualification 结果，没有重复运行。生产路线仍优先 OTBN/HMAC。

当前另有 Verilator 实测：Ibex 复位启动、真实 ROM 执行、mailbox INIT/VERSION 及 USB PE/EP0 数字线级集成（见下节）。注册、认证和掉电恢复仍未验证。
测试熵固定为重复字节，仅用于可重复测试。未计退休指令数；没有 Ibex cycle/性能测量。
macOS 上 Unicorn 回调触发 libffi trampoline 断言，改用无回调水位法，
所以没有最小 SP 动态轨迹或精确峰值。不能把 Unicorn 指令执行时间换成 Ibex cycles。

## 移植接口实际状态

`firmware/port/platform.c` 实现 freestanding 内存操作、单循环线程替代、
按钮软件锁存及 mailbox 寄存器访问。详细地址/命令见 `firmware/README.md`。
`soc_memory_mailbox.sv` 已提供实际 CPU 总线、ROM、16 KiB 推断 RAM、mailbox、微秒 timer 与同步按键锁存。
RNG 与 NVM 仍是外部契约；测试中的确定性熵和非持久 NVM 不能当作真实设备服务。
RNG 无 ready 时 fail closed；无熵健康测试。NVM 错误时停机，但尚无原子性/断电保证。
现有 attestation 页为未配置状态，注册不会成功返回真实证书。
上游 provisioning vendor APDU 仍保留，必须在正式生产配置中限制或关闭；
短 APDU、长度/证书边界、计数器页满和坏输入路径尚未资格验证。

`soc/rtl/soc_boundary_top.sv` 是 Ibex + P0 USB PE 的可综合边界，不含 CPU/USB 互连。
它把存储接口、端点控制与 debug request 暴露给外部。不能据此宣称固件能在该顶层启动。

## GF180 映射实测

OpenTitan 固定到 `2e20836f9c9787bad82c84b5ba704223f06c8890`，包含所用 Ibex。
Yosys 0.69 + slang，GF180 `gf180mcu_fd_sc_mcu7t5v0` TT 25°C 3.3V Liberty，
`hierarchy -check; synth; dfflibmap; abc; stat`。无布局寄生/时序约束优化。
脚本及 workaround 见 `soc/README.md`，完整生成日志、netlist、输入 hash 在 `soc/build/`，
可审阅摘要与 manifest 在 `soc/evidence/`。

- **Ibex RV32IMC：374,272.8192 µm² = 0.374273 mm²**，FF 寄存器文件、fast M、无 I-cache。
  显式 `RV32ZC=RV32Zca`；此前默认扩展配置 381,624.5440 µm² 不再作为预算依据。
- **P0 两端点 `usb_fs_nb_pe` 包装：42,090.7648 µm²**，复用 P0 SS 映射结果作保守预算。
  P0 TT 是 39,853.8560 µm²；与本次其他块 TT 并非同一 corner，不能把相加值称完整同角 SoC PPA。
- **完整 OpenTitan `usbdev`：1,982,875.8656 µm² = 1.982876 mm²**。
  这里内部 generic packet SRAM 被展开为标准单元，不是硬宏映射；
  因此只说明“当前导出实现”超过 quarter core，不能证明任何宏适配后的 usbdev 都放不下。
- **实际固件 combinational ROM：293,006.5152 µm² = 0.293007 mm²**。
  从 ELF PT_LOAD 的 ROM 物理地址生成 32 KiB 地址窗、未使用字填零；不是随机 ROM 或估算每 bit 面积。
  没有时序闭合，后续可能需要寄存输出/等待状态；固件内容改变须重测。
- **PULP dm_top：101,855.0848 µm²；dmi_jtag：43,890.8288 µm²**，
  debug 合计 0.145746 mm²。它们独立映射，尚未连接总线、认证/锁定或生命周期门控。
- CPU + PE 暴露边界顶层：393,790.3424 µm²。常量连接和全局优化使其不同于独立块面积相加。
  此结果没有 ROM/RAM/debug，不能单独用作 SoC 尺寸。

## 存储和 slot 容量判断

实际取得 OCD 1024×8 SRAM LEF，版本 `d41c7447d34d0c298158094378c8268560941724`，
尺寸 **301.300 × 515.810 µm = 0.155414 mm² / KiB**。1024×32 需要四条 byte lane；
8 KiB 需八片，16 KiB 需十六片。当前无 ECC；若加入 ECC/加扰，需另计容量和控制成本。
本地几何证据不足以证明宏可流片；没有完成兼容 Liberty/GDS、时序、电源和访问接口验证。

复用仓库 slot YAML：quarter core 1.732644 mm²（1052 × 1647 µm）；
0.5×1 core 4.458376 mm²；1×0.5 core 5.020056 mm²；1×1 core 12.917424 mm²。
这是模板 core 几何，不是可用标准单元面积。没有改 pad 环或假设自绑线扩大 core。

CPU + 轻 PE + 实际 ROM + debug 的块面积预算为 0.855116 mm²（本次 ROM GF180 映射 0.293007 mm²）。
加 16 KiB SRAM 本体 2.486617 mm²，已达 **3.341733 mm²**；
按“标准单元 50% 利用率 + 宏 10% 面积余量”的规划假设为 **4.445510 mm²**，
还没包括总线、端点/EP0、FIFO、RNG、timer、GPIO、NVM/QSPI、时钟复位、电源与 PHY。
计算式为 `0.855116 / 0.50 + 2.486617 × 1.10 = 4.445510 mm²`。
50% 只用于标准单元部分的规划利用率，宏按本体面积加 10% 假设余量；
不是整个 core 的统一利用率。这个 10% 不是已经放好的几何 halo。
未计模块既没有隐含在利用率中，也没有被实测；4.446 mm² 不能称作完整 SoC 面积或完成 floorplan。

- **quarter slot：仅对所选 OCD SRAM 宏 + 当前 16 KiB 配置明确排除**，仅 SRAM 本体已超 core。
  16 KiB 是本次链接/测量配置，不是测得的最小 RAM 需求；结论不外推至其他 SRAM 宏或完整优化后的实现。
  即使假设缩至 8 KiB，宏 1.243308 + 已测块 0.855116 = **2.098424 mm²**，仍超 core；
  8 KiB 也尚未经过完整协议栈峰值验证。当前软件参考后端静态 RAM 已 9,760 B，8 KiB 场景无法容纳；16 KiB 仍非实测最小需求，OT 后端需重测。
- **1×0.5：轻 PE + 16 KiB 是值得推进 floorplan 的候选**；4.446 mm² 的假设预算与
  5.020 mm² core 之间仍需容纳全部未测模块，不能承诺 fit。0.5×1 的 4.458 mm² 更紧，
  且宽度/宏排列不同，不能只按面积互换。
- **1×1：为完整 usbdev/集成余量提供更多空间**。当前 generic usbdev + 16 KiB RAM +
  CPU/ROM/debug 的实体块面积 5.282518 mm²，规划假设约 **8.327881 mm²**；
  宏适配可改变 usbdev 数字，仍需实际完整实现和布线。
- **外部 QSPI 程序存储：可作为开发/较小 slot 的优化候选**，当前固件常量 ROM 仅 0.293007 mm²，
  移出程序并不能解决 16 KiB SRAM 本体超过 quarter core 的问题。
  QSPI/XIP/boot ROM/校验与密钥保护成本未测，不能直接把 ROM 面积全部当净节省。
  若外存承载密钥，必须有明确的认证/保密/防回滚及受保护根密钥方案。

`capacity.json` 保留上述算术场景，可由 `soc/report.py` 重建。
**没有已通过的物理 floorplan**：OpenROAD 存在，但未找到完整可用的技术 LEF/宏 Liberty+GDS
PDK 安装；只有标准单元 Liberty 和单片 SRAM LEF。不能据此生成可信的 SoC placement/routing。
宏数量和矩形几何只能提供容量筛查，不能声称拥塞、CTS、48 MHz、DRC/LVS 已通过。
P0 的 PE STA 不能外推为 CPU/ROM/SoC 的时序。

## 后续验收门槛

1. 实现同一 RTL 的 CPU 总线/ROM/RAM、mailbox、EP0/枚举、HID endpoints、timer/button、
   RNG 和 NVM；用当前 ELF 从复位启动，在 RTL 中完成枚举、INIT/PING/VERSION、
   注册/认证/check-only、错误与超时、多包/重传、按键和密钥跨复位持久性测试。
2. 按独立评估结果接入优先的 OTBN/HMAC 组合，再测密码向量、边界与错误路径；测真实注册/认证最坏路径的
   min-SP、heap（当前无）、中断栈和 Ibex cycles；报告频率、等待状态和测试输入。
3. FPGA 接真实主机，以同一 RTL/固件验证 Linux/浏览器或 libfido2 主机、枚举、
   注册/认证、按钮、拔插/掉电、错误 RNG/NVM；板级成功也不等于 GF180 PHY 通过。
4. 明确制造 provisioning、attestation 访问控制、调试锁定、根密钥、更新验证、
   存储原子性/磨损/计数器单调性。GF180 eFuse **不是 OpenTitan OTP 的直接替代**：
   宏协议、电压、ECC/加扰、生命周期握手和制造测试都需适配及证据。
5. 拿到真实 PDK/存储宏后做完整集成综合、macro placement、供电、CTS、route、
   多 corner STA、DRC/LVS；再冻结 slot。PHY 工作继续由既有独立负责人处理。

验证记录：参考固件 strict-warning 编译、既有 native/RV32 密码 qualification PASS，
实际 Ibex mailbox INIT/VERSION PASS；资源 evidence 已由 `soc/report.py` 更新。
数字 USB 测试另见下节。没有完成注册/认证、持久性、物理 floorplan 或安全签核。

## USB 数字线级集成验证（2026-11-16）

新增 `soc/rtl/usb_u2f_bridge.sv` 与 `soc/rtl/soc_usb_top.sv`：同一真实 Ibex、
当前 ELF 的 ROM、推断 RAM/mailbox 与既有两端点 OpenTitan USB PE 相连。
`PYTHONPATH=soc/.tools:firmware/.tools python3 soc/test_usb.py` 使用独立 CRC/NRZI
编码的 C++ 主机驱动实际数字 D+/D− 输入，解码设备输出；证据为
`soc/evidence/usb-rtl.json`（ELF/RTL/测试输入哈希）及 `soc/build/usb-rtl.log`。

已验证设备/配置/HID report 描述符、短描述符、SET_ADDRESS 状态包 ACK 后才生效、
未 ACK 重试、SET_CONFIGURATION、真实固件 HID INIT 与 U2F_VERSION `U2F_V2 9000`、
错误 CRC OUT 丢弃、重复 OUT 抑制、未知请求 STALL 后新 SETUP 恢复、外部 link reset
清零地址及描述符超时重试。它比 mailbox-only 测试前进了一步，但仍不是实体 USB 主机枚举。

**明确测试 stub/限制：** `soc_usb_top` 的 NVM 为擦除态读、写命令确认后丢弃的
非持久 stub；之前将写入直接拒绝会使初始化停机，不能将此 stub 当成密钥存储。
RNG 是外部接口，仿真提供固定测试字节；无健康测试/真实熵。按键置未按下，debug 关闭。
USB 复位由外部显式信号注入，尚无 VBUS/pullup/attach、总线 SE0 复位检测或模拟 PHY；
VID/PID 0000 仅开发占位。EP0 描述符均小于 64 B，没有实现任意多包控制传输、字符串、
完整 HID/USB 请求合法性检查、endpoint halt、suspend/resume；不能宣称 USB 合规。
USB reset 与固件 mailbox 状态的全路径恢复仍需测试。新增桥未做完整 GF180 综合/PPA，
故容量报告仍将其列为未测成本；未借 generic SRAM 面积否决完整 OT usbdev。

Checkpoint 1 仍缺真实注册/认证、跨掉电持久密钥、OTBN/HMAC 实际组合、真实熵、
正式安全生命周期/调试控制以及完整物理实现。当前优先路线与独立 OT 负责人保持一致。
