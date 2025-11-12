// 8-bit counter with synchronous reset
// Design Under Test (DUT) for Verilator simulation verification

`timescale 1ns / 1ps

module counter (
    input  logic       clk,      // Clock input
    input  logic       rst_n,    // Active-low synchronous reset
    output logic [7:0] count,    // 8-bit counter output
    output logic       overflow  // Overflow flag (goes high when counter wraps)
);

    // Counter logic
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            count <= 8'h00;
        end else begin
            count <= count + 1'b1;
        end
    end

    // Combinational overflow flag - high when count is at maximum
    assign overflow = (count == 8'hFF);

endmodule
