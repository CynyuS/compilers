use std::env;
use std::process;

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
