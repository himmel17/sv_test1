// C++ testbench wrapper for Verilator
// This file provides the main() function to drive the simulation

#include <verilated.h>
#include "Vcounter_tb.h"

#if VM_TRACE
#include <verilated_vcd_c.h>
#endif

int main(int argc, char** argv) {
    // Initialize Verilator
    Verilated::commandArgs(argc, argv);

    // Create instance of testbench module
    Vcounter_tb* tb = new Vcounter_tb;

#if VM_TRACE
    // Enable waveform tracing
    Verilated::traceEverOn(true);
    VerilatedVcdC* tfp = new VerilatedVcdC;
    tb->trace(tfp, 99);  // Trace 99 levels of hierarchy
    tfp->open("sim/waves/counter.vcd");
#endif

    // Simulation time
    vluint64_t sim_time = 0;
    const vluint64_t max_sim_time = 100000;  // Maximum simulation time

    // Run simulation
    while (!Verilated::gotFinish() && sim_time < max_sim_time) {
        // Evaluate model
        tb->eval();

#if VM_TRACE
        // Dump waveform
        if (tfp) tfp->dump(sim_time);
#endif

        // Increment time
        sim_time++;
    }

    // Final model cleanup
    tb->final();

#if VM_TRACE
    // Close trace file
    if (tfp) {
        tfp->close();
        delete tfp;
    }
#endif

    // Cleanup
    delete tb;

    return 0;
}
