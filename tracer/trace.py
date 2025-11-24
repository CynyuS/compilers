"""
TRACING!
Cynthia Shao and Jonathan Brown

This script takes in a Bril json file and an array of instructions executed in a trace
and returns an optimized version with speculate and commits.
"""

import subprocess
import json
import sys
import re
import argparse

ARGS_RE = r"TRACE_ARG: (.*)"

def run_cmd(cmd):
    """
    run shell commands and return stdout
    """
    result = subprocess.run(
      cmd,
      shell=True,
      capture_output=True,
      text=True
    )
    
    if result.returncode != 0:
      print(f"Error running: {cmd}", file=sys.stderr)
      print(result.stderr, file=sys.stderr)
      sys.exit(1)
    
    return result.stdout
  
def main():
  parser = argparse.ArgumentParser(description='Trace and optimize Bril programs')
  parser.add_argument('-f', '--file', action='store_true', 
                      help='Read from file (default behavior)')
  parser.add_argument('-std', '--stdin', action='store_true',
                      help='Read from stdin (for brench compatibility)')
  parser.add_argument('input', nargs='?', help='Input Bril file (or args if using stdin)')
  parser.add_argument('args', nargs='*', help='Program arguments')
  
  parsed_args = parser.parse_args()
  
  # Determine mode
  if parsed_args.stdin or (not parsed_args.file and not parsed_args.input):
    # Stdin mode: read Bril from stdin, args from command line
    bril = sys.stdin.read()
    result = subprocess.run(
        ["bril2json"],
        input=bril,
        text=True,
        capture_output=True
    )
    if result.returncode != 0:
        print(f"Error running bril2json", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    bril_json = result.stdout
    match = re.search(ARGS_RE, bril)
    args = match.group(1) if match else ""
    program_args = [args]
  else:
    # File mode: read from file
    if not parsed_args.input:
      parser.error("File path required when not using stdin mode")
    bril = parsed_args.input
    program_args = parsed_args.args
    bril_json = run_cmd(f"bril2json < {bril}")
  
  original_program = json.loads(bril_json)
  
  # Run with brili to get trace
  args_str = " ".join(program_args)
  if parsed_args.stdin or (not parsed_args.file and not parsed_args.input):
    # In stdin mode, pipe the already-read Bril content
    trace_output = subprocess.run(
      f"brili -t {args_str}".split(),
      input=bril_json,
      text=True,
      capture_output=True
    ).stdout
  else:
    # In file mode, use the original command
    trace_output = run_cmd(f"bril2json < {bril} | brili -t {args_str}")
  
  trace = []
  actual_output = []
  for line in trace_output.strip().split('\n'):
    if line:
      try:
        instr = json.loads(line)
        # Only add dictionaries (instructions) to trace
        if isinstance(instr, dict):
          trace.append(instr)
        else:
          # This is program output (numbers, strings, etc.)
          actual_output.append(str(instr))
      except json.JSONDecodeError:
        actual_output.append(line)

  transformed_trace, side_effects_trace = guard_trace(trace)
  stitched_program = stitch_trace(original_program, transformed_trace, side_effects_trace)
  # optimized_program = optimize(stitched_program)
  json.dump(stitched_program, sys.stdout, indent=2)

def guard_trace(trace):
  new_trace = []
  side_effects = []
  
  for instr in trace:
    # Skip labels and jumps in trace
    if "label" in instr or instr.get("op") == "jmp":
      continue
    elif "op" in instr and instr.get("op") == "print":
      side_effect = instr.copy()
      side_effects.append(side_effect)
      continue
    # Convert branches to guards
    elif instr.get("op") == "br":
      new_instr = {
          "op": "guard",
          "args": instr["args"],
          "labels": ["original_code"]
      }
    else:
      new_instr = instr.copy()
    
    new_trace.append(new_instr)
  
  return new_trace, side_effects

def stitch_trace(program, trace, sd_effects):
  main_func = None
  for func in program["functions"]:
    if func["name"] == "main":
      main_func = func
      break
    
  if not main_func:
    print("error no main found")
    sys.exit(1)
    
  new_instrs = []
  
  new_instrs.append({"op": "speculate"})
  has_return = trace and trace[-1].get('op') == 'ret'
  if has_return:
    new_instrs.extend(trace[:-1])
    new_instrs.append({"op": "commit"})
    new_instrs.extend(sd_effects)
    new_instrs.append(trace[-1])
  else:
    new_instrs.extend(trace)
    new_instrs.append({"op": "commit"})
  
  new_instrs.append({'label': 'original_code'})

  new_instrs.extend(main_func['instrs'])
  
  main_func['instrs'] = new_instrs
  
  return program

if __name__ == "__main__":
  main()