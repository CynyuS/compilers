use std::env;
use std::process;
use std::io::{self, Read};

mod bril_parse;
mod ast;
mod cfg;
mod basic_block;
mod dce;

use bril_parse::BrilParser;
use ast::ProgramAST;
use dce::DeadCodeElimination;

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut buffer = String::new();

    let program = if args.len() > 1 {
        // Option to read from file
        eprintln!("Input: {} <bril_json_file>", args[0]);
    
        // Parse the Bril program
        match BrilParser::from_file(&args[1]) {
            Ok(prog) => prog,
            Err(e) => {
                eprintln!("Error parsing Bril program: {}", e);
                process::exit(1);
            }
        }
    } else {
        io::stdin().read_to_string(&mut buffer).unwrap();
        match BrilParser::from_string(&buffer) {
            Ok(prog) => prog,
            Err(e) => {
                eprint!("Error parsing Bril program from stdin: {}", e);
                process::exit(1);
            }
        }
    };

    

    // Build AST representation
    let mut program_ast = ProgramAST::from_bril_program(program);
    
    // Print original CFG
    println!("Original CFG edges:");
    for function in &program_ast.functions {
        println!("Function: {}", function.name);
        let edges = function.cfg.get_edges();
        for (block_name, successors) in edges {
            println!("  {} -> {:?}", block_name, successors);
        }
    }

    // Apply dead code elimination pass
    let dce_pass = DeadCodeElimination::new();
    program_ast.apply_pass(Box::new(dce_pass));
    
    // Print basic blocks
    println!("Basic Blocks:");
    for function in &program_ast.functions {
        println!("Function: {}", function.name);
        let blocks = function.cfg.get_blocks();
        for (block_name, basic_blocks) in blocks {
            println!("  {:?} -> {:?}", block_name, basic_blocks);
        }
    }
    
    // Print optimized CFG
    println!("\nOptimized CFG edges:");
    for function in &program_ast.functions {
        println!("Function: {}", function.name);
        let edges = function.cfg.get_edges();
        for (block_name, successors) in edges {
            println!("  {} -> {:?}", block_name, successors);
        }
    }

}
