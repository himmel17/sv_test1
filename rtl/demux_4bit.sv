// 4-bit 1:4 Demultiplexer
// Design Under Test (DUT) for Verilator simulation verification

`timescale 1ns / 1ps

module demux_4bit (
    input  logic [3:0] data_in,   // 4-bit data input
    input  logic [1:0] sel,       // 2-bit select signal (0-3)
    output logic [3:0] out0,      // Output 0
    output logic [3:0] out1,      // Output 1
    output logic [3:0] out2,      // Output 2
    output logic [3:0] out3       // Output 3
);

    // Demultiplexer logic
    // Route input to selected output, others are 0
    always_comb begin
        // Default: all outputs to 0
        out0 = 4'h0;
        out1 = 4'h0;
        out2 = 4'h0;
        out3 = 4'h0;

        // Route input to selected output
        case (sel)
            2'b00: out0 = data_in;
            2'b01: out1 = data_in;
            2'b10: out2 = data_in;
            2'b11: out3 = data_in;
        endcase
    end

endmodule
