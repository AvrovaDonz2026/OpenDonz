// CPU + actual ROM + inferred RAM + mailbox. USB PE/EP0 not attached yet.
module soc_firmware_top(
 input logic clk_i, rst_ni, debug_req_i,
 input logic [511:0] hid_rx_i, input logic hid_rx_valid_i, output logic hid_rx_ready_o,
 output logic [511:0] hid_tx_o, output logic hid_tx_valid_o, input logic hid_tx_ready_i,
 input logic button_i, rng_valid_i, input logic [7:0] rng_data_i, output logic rng_ready_o,
 output logic nvm_req_o, nvm_we_o, output logic [31:0] nvm_addr_o,
 output logic [7:0] nvm_wdata_o, output logic [2:0] nvm_command_o,
 input logic nvm_ready_i, nvm_error_i, input logic [31:0] nvm_rdata_i
);
 logic instr_req_o, instr_gnt_i, instr_rvalid_i;
 logic [31:0] instr_addr_o, instr_rdata_i;
 logic data_req_o, data_we_o, data_gnt_i, data_rvalid_i, data_err;
 logic [3:0] data_be_o;
 logic [31:0] data_addr_o, data_wdata_o, data_rdata_i;
  ibex_top #(.RV32M(ibex_pkg::RV32MFast), .RV32B(ibex_pkg::RV32BNone),
    .RV32ZC(ibex_pkg::RV32Zca), .ICache(0), .SecureIbex(0)) cpu (
    .clk_i, .rst_ni, .test_en_i(1'b0), .scan_rst_ni(1'b1),
    .hart_id_i(32'b0), .boot_addr_i(32'b0),
    .cheriot_enable_i(ibex_pkg::IbexMuBiOff), .trvk_heap_base_addr_i(32'b0),
    .ram_cfg_icache_tag_i('0), .ram_cfg_icache_data_i('0),
    .instr_req_o, .instr_addr_o, .instr_gnt_i, .instr_rvalid_i, .instr_rdata_i,
    .instr_rdata_intg_i('0), .instr_err_i(1'b0),
    .data_req_o, .data_we_o, .data_be_o, .data_addr_o, .data_wdata_o,
    .data_gnt_i, .data_rvalid_i, .data_rdata_i, .data_rdata_intg_i('0),
    .data_tag_i(1'b0), .data_err_i(data_err),
    .trvk_revbm_gnt_i(1'b0), .trvk_revbm_rvalid_i(1'b0),
    .trvk_revbm_rdata_i('0), .trvk_revbm_rdata_intg_i('0), .trvk_revbm_err_i(1'b0),
    .irq_software_i(1'b0), .irq_timer_i(1'b0), .irq_external_i(1'b0),
    .irq_fast_i('0), .irq_nm_i(1'b0), .debug_req_i,
    .scramble_key_valid_i(1'b0), .scramble_key_i('0), .scramble_nonce_i('0),
    .fetch_enable_i(ibex_pkg::IbexMuBiOn), .mcounteren_writable_i(ibex_pkg::IbexMuBiOff)
  );

 soc_memory_mailbox memory_bus(
 .clk_i, .rst_ni, .instr_req_i(instr_req_o), .instr_addr_i(instr_addr_o),
 .instr_gnt_o(instr_gnt_i), .instr_rvalid_o(instr_rvalid_i), .instr_rdata_o(instr_rdata_i),
 .data_req_i(data_req_o), .data_we_i(data_we_o), .data_be_i(data_be_o),
 .data_addr_i(data_addr_o), .data_wdata_i(data_wdata_o), .data_gnt_o(data_gnt_i),
 .data_rvalid_o(data_rvalid_i), .data_err_o(data_err), .data_rdata_o(data_rdata_i),
 .hid_rx_i, .hid_rx_valid_i, .hid_rx_ready_o, .hid_tx_o, .hid_tx_valid_o, .hid_tx_ready_i,
 .button_i, .rng_valid_i, .rng_data_i, .rng_ready_o,
 .nvm_req_o, .nvm_we_o, .nvm_addr_o, .nvm_wdata_o, .nvm_command_o,
 .nvm_ready_i, .nvm_error_i, .nvm_rdata_i
 );
endmodule
