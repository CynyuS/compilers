use std::env;
use std::process;

mod bril_parse;
mod cfg;

use bril_parse::BrilParser;
use cfg::ControlFlowGraph;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        eprintln!("Input: {} <bril_json_file>", args[0]);
        process::exit(1);
    }

    let file_path = &args[1];
    
    // Parse the Bril program
    let program = match BrilParser::from_file(file_path) {
        Ok(prog) => prog,
        Err(e) => {
            eprintln!("Error parsing Bril program: {}", e);
            process::exit(1);
        }
    };

    // Build the control flow graph
    let cfg = ControlFlowGraph::from_program(&program);
    
    // Output the CFG
    println!("{:?}", cfg.get_edges());
}
