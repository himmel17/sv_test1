// Testbench for 4-bit 1:4 Demultiplexer
// Verifies demux functionality with automatic checking

`timescale 1ns / 1ps

module demux_4bit_tb #(
    parameter SIM_TIMEOUT = 10000  // Simulation timeout in timescale units (default: 10us)
);

    // Signals
    logic [3:0] data_in;
    logic [1:0] sel;
    logic [3:0] out0, out1, out2, out3;

    // Test counters
    int         error_count;
    int         active_outputs;   // For output isolation test

    // Instantiate DUT
    demux_4bit dut (
        .data_in(data_in),
        .sel(sel),
        .out0(out0),
        .out1(out1),
        .out2(out2),
        .out3(out3)
    );

    // VCD dump for GTKWave
    initial begin
        $dumpfile("sim/waves/demux_4bit.vcd");
        $dumpvars(0, demux_4bit_tb);
    end

    // Helper task to check outputs
    task check_outputs;
        input [3:0] exp_out0;
        input [3:0] exp_out1;
        input [3:0] exp_out2;
        input [3:0] exp_out3;
        begin
            if (out0 !== exp_out0) begin
                $display("ERROR at Time=%0t: out0=%h, expected=%h (sel=%d, data_in=%h)",
                         $time, out0, exp_out0, sel, data_in);
                error_count++;
            end
            if (out1 !== exp_out1) begin
                $display("ERROR at Time=%0t: out1=%h, expected=%h (sel=%d, data_in=%h)",
                         $time, out1, exp_out1, sel, data_in);
                error_count++;
            end
            if (out2 !== exp_out2) begin
                $display("ERROR at Time=%0t: out2=%h, expected=%h (sel=%d, data_in=%h)",
                         $time, out2, exp_out2, sel, data_in);
                error_count++;
            end
            if (out3 !== exp_out3) begin
                $display("ERROR at Time=%0t: out3=%h, expected=%h (sel=%d, data_in=%h)",
                         $time, out3, exp_out3, sel, data_in);
                error_count++;
            end
        end
    endtask

    // Test sequence
    initial begin
        // Initialize
        error_count = 0;
        data_in = 4'h0;
        sel = 2'b00;

        $display("=== Starting 4-bit DEMUX Testbench ===");

        // Test each select value with multiple data patterns
        // Test patterns: 0x0, 0xF, 0x5, 0xA
        for (int s = 0; s < 4; s++) begin
            $display("Time=%0t: Testing sel=%d", $time, s);

            for (int d = 0; d < 4; d++) begin
                sel = s[1:0];
                // Apply test pattern based on iteration
                case (d)
                    0: data_in = 4'h0;
                    1: data_in = 4'hF;
                    2: data_in = 4'h5;
                    3: data_in = 4'hA;
                endcase
                #10;  // Wait for combinational logic to settle

                // Calculate expected outputs
                case (sel)
                    2'b00: check_outputs(data_in, 4'h0, 4'h0, 4'h0);
                    2'b01: check_outputs(4'h0, data_in, 4'h0, 4'h0);
                    2'b10: check_outputs(4'h0, 4'h0, data_in, 4'h0);
                    2'b11: check_outputs(4'h0, 4'h0, 4'h0, data_in);
                endcase

                // Display progress
                if (error_count == 0) begin
                    $display("   sel=%d, data_in=0x%h: PASS (out%0d=0x%h)",
                             sel, data_in, sel,
                             (sel==0) ? out0 : (sel==1) ? out1 : (sel==2) ? out2 : out3);
                end
            end
        end

        // Test all outputs simultaneously show zero when not selected
        $display("Time=%0t: Testing output isolation", $time);
        for (int s = 0; s < 4; s++) begin
            sel = s[1:0];
            data_in = 4'hF;
            #10;

            // Count how many outputs are non-zero
            active_outputs = 0;
            if (out0 != 4'h0) active_outputs++;
            if (out1 != 4'h0) active_outputs++;
            if (out2 != 4'h0) active_outputs++;
            if (out3 != 4'h0) active_outputs++;

            if (active_outputs != 1) begin
                $display("ERROR at Time=%0t: Expected exactly 1 active output, got %0d",
                         $time, active_outputs);
                error_count++;
            end
        end

        // Test summary
        #10;
        $display("=== Test Completed ===");
        $display("Total test cases: 16 (4 selects × 4 data patterns)");
        if (error_count == 0) begin
            $display("*** PASSED: All tests passed successfully ***");
        end else begin
            $display("*** FAILED: %0d errors detected ***", error_count);
        end

        // Finish simulation
        #50;
        $finish;
    end

    // Timeout watchdog
    initial begin
        #SIM_TIMEOUT;
        $display("ERROR: Simulation timeout after %0d time units", SIM_TIMEOUT);
        $finish;
    end

endmodule
