// Testbench for 8-bit counter
// Verifies counter functionality with automatic checking

`timescale 1ns / 1ps

module counter_tb #(
    parameter SIM_TIMEOUT = 50000  // Simulation timeout in timescale units (default: 50us)
);

    // Clock and reset signals
    logic       clk;
    logic       rst_n;
    logic [7:0] count;
    logic       overflow;

    // Expected counter value for checking
    logic [7:0] expected_count;
    int         error_count;

    // Instantiate DUT
    counter dut (
        .clk(clk),
        .rst_n(rst_n),
        .count(count),
        .overflow(overflow)
    );

    // Clock generation (10ns period = 100MHz)
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    // VCD dump for GTKWave
    initial begin
        $dumpfile("sim/waves/counter.vcd");
        $dumpvars(0, counter_tb);
    end

    // Test sequence
    initial begin
        // Initialize
        error_count = 0;
        expected_count = 8'h00;
        rst_n = 0;

        // Reset sequence
        $display("=== Starting Counter Testbench ===");
        $display("Time=%0t: Asserting reset", $time);
        repeat(5) @(posedge clk);

        @(negedge clk);  // Wait for negative edge before releasing reset
        rst_n = 1;
        $display("Time=%0t: Releasing reset", $time);

        // Test normal counting for full cycle (256 counts)
        $display("Time=%0t: Testing normal counting operation", $time);
        for (int i = 0; i < 270; i++) begin
            // Update expected value before clock edge
            expected_count = expected_count + 1;

            @(posedge clk);
            #1;  // Small delay to allow signals to settle

            // Check counter value
            if (count !== expected_count) begin
                $display("ERROR at Time=%0t: count=%0d, expected=%0d",
                         $time, count, expected_count);
                error_count++;
            end

            // Check overflow flag (should be high when count is 255)
            if (expected_count == 8'hFF && !overflow) begin
                $display("ERROR at Time=%0t: overflow flag not set at max count", $time);
                error_count++;
            end else if (expected_count != 8'hFF && overflow) begin
                $display("ERROR at Time=%0t: overflow flag incorrectly set", $time);
                error_count++;
            end

            // Display progress at key points
            if (count == 8'h00 || count == 8'hFF || count % 64 == 0) begin
                $display("Time=%0t: count=%3d (0x%02h), overflow=%b",
                         $time, count, count, overflow);
            end
        end

        // Test reset during operation
        $display("Time=%0t: Testing reset during counting", $time);
        rst_n = 0;
        repeat(3) @(posedge clk);
        #1;  // Check that reset is holding counter at 0
        if (count !== 8'h00) begin
            $display("ERROR at Time=%0t: Reset not holding, count=%0d", $time, count);
            error_count++;
        end

        rst_n = 1;
        @(posedge clk);
        #1;
        expected_count = 8'h01;  // After reset release, counter increments to 1

        if (count !== expected_count) begin
            $display("ERROR at Time=%0t: Post-reset failed, count=%0d, expected=%0d",
                     $time, count, expected_count);
            error_count++;
        end

        // Test summary
        $display("=== Test Completed ===");
        if (error_count == 0) begin
            $display("*** PASSED: All tests passed successfully ***");
        end else begin
            $display("*** FAILED: %0d errors detected ***", error_count);
        end

        // Finish simulation
        #100;
        $finish;
    end

    // Timeout watchdog
    initial begin
        #SIM_TIMEOUT;
        $display("ERROR: Simulation timeout after %0d time units", SIM_TIMEOUT);
        $finish;
    end

endmodule
