these are general guidelines for any code, script, design, or documentation
that will ever be written by you in any part of this repository. you
must follow these. if there is ambiguity in my description or guidance 
at any point, you must stop and ask me for clarification.

this repository is meant to hold a large project centered around the
design and implementation of the stack-based ZPU processor and a software
stack for it.

    * any work done at any point must be its own commit.
    * do not make "polluted" commits that touch parts of the code that are
      not related to each other. break those up into smaller, separate
      commits
    * do not do make abstractions that were not asked for, add features that
      were not requested, or  
    * there must not be any dead code
    * minimize comments. make the code clear through functions and naming
      and control flow.
    * do not refrecence prompts or "break the fourth wall". write code as a
      human would, for other humans to read. this is especially important
      since all code will be maintained by experienced programmers that do
      not need basic concepts or design decisions to be explained to them
      by inline comments
    * always be as concise as possible
    * don't touch code you didn't write

your workflow should follow:
    * first writing a design/spec in the form of header files, or
      similar design docs
    * writing tests based only on the design/spec
    * writing the actual implementations
if it any point it is apparent that a previous step was not completed 
to a good enough extent (e.g. missed an error handling case), stop, go
back, add that, then work your way back down to the later steps
ideally, you will be launching new agents for each of these

for code written as part of large repositories (e.g. LLVM, QEMU, GDB),
you must adhere to their individual coding guidelines. never create
pull requests into them for any reason.

otherwise, you must stick to 80 columns, 4-spaced tabs.

be extremely concise during chats. i do not want bullet points or buzz
words or anything like that. use as few words as possible to talk.

never touch the Dockerfile, or docker.sh

never run useless complicated bash commands if it's easier to just ask
me something

do not use .md files. always go for simple .txt files.

always write in all lowercase for sentences/titles in docs. always
prefer an extra line spacing over (-s) or (=s) for marking sections

