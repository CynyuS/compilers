/// Pseudocode:
/// Given a single basic block.
/// Constructing a value table
/// [ [(str, num, num), str], ... ]
/// [(op, arg, arg), C.H.]
/// index = value number
/// instructions come in the form: 
/// dest, op, value/args
/// for every instruction in the basic block:
///     if args:
///         value = (op, args[0], ...)
///     else:
///         value = (op, value)
///     
///     if value in value table: // reuse the table
///         num, var = table[value]
///         replace instr with copy of var
///     else: // value not computed before, update table
///         num = new value number
///            
///         // if we rewrite a variable... :o
///         // ez thought: get rid of all variable names, based off of values
///         // literally renaming every variable in every block.
///         // lazier approach: only rename when it's overwritten... only rename non-unique
///         // must put things back to where they were for other basic blocks.
///         dest = instr.dest
///         if dest will be overwritten later: :(
/// 
///         table[value] = num, dest
///         
///         reconstruct the instruction
///         relookup the operands to get their canonical homes
///         do it in place.. rewrite the args.
///         get the args, get the value number, row in table, back to variable name
/// Constructing the bubble to get get num for where the instruction will point to in the bubble
// think outside in!