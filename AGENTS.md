# Instructions for Claude

This file is read at the start of every Claude Code session in this folder. It tells Claude how to work *with me* on *this project*. Edit it as you learn what works.

---

## About me

I'm a non-coder who builds things by describing them in plain English. Treat me like a smart product owner, not a developer. I can read code reasonably but don't want to write it.

## How to communicate

- **Explain in plain English first, code second.** Before showing me code, tell me what you're going to do and why, in a few sentences.
- **No jargon without translation.** If you have to use a term like "API," "promise," "state," or "deploy," give me the one-sentence plain meaning the first time.
- **Show me what you changed.** When you edit a file, summarize the change in one sentence ("I added a button to the homepage that opens a modal") before or after the diff.
- **Ask before large changes.** If a task involves changing more than 3 files or installing a new dependency, pause and confirm with me first.
- **Surface trade-offs.** If there's a "fast and ugly" vs. "slower and cleaner" path, tell me both and let me choose.
- **One change at a time.** Don't bundle unrelated improvements into one step. I want to learn what each change does.

## How to work

- **Run things and check the output.** Don't just write code and hand it to me — actually run it, see what happens, and tell me whether it worked.
- **Fail loudly, not silently.** If something errors, show me the error and your hypothesis before trying random fixes.
- **Prefer boring, popular tools.** When choosing a library or framework, pick the one with the most tutorials and Stack Overflow answers, not the newest.
- **Keep dependencies minimal.** Don't add a library if 15 lines of code would do.
- **Save my work to Git.** After we finish a meaningful change, suggest a commit message and ask me to confirm before committing.

## Project context

> Edit these as the project grows. They're the most important thing for Claude to know.

- **What it is:** A Homebrew Channel catalog generator that turns non-official awesome-webos apps into one `dist/repo.json`.
- **Who it's for:** Friends / public webOS homebrew users (and me).
- **Tech stack:** Python 3 + PyYAML + jsonschema; GitHub Actions; no web frontend.
- **Where it runs:** Generated on a laptop or in GitHub Actions; users add the raw `dist/repo.json` URL in Homebrew Channel.

## Things I've tried that didn't work

> Add to this list as we go. Saves repeating mistakes in future sessions.

- (none yet)

## Things I've learned that I want to remember

> Things Claude figured out that I want kept in mind for future work.

- (none yet)
