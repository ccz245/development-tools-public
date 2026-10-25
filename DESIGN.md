# Design

## Public, and separate from the private repo

This repo is public so any machine that can reach github.com can read or clone it with no
invitation or sign-in. A private repo on a personal account cannot be shared with Enterprise
Managed User accounts, which some corporate environments use exclusively.

It was started fresh rather than by flipping the private `development-tools` repo to public,
so no earlier history can carry private detail into public view.

**Risk:** everything here is world-readable, indexed and archived. Nothing personal, secret,
or identifying a client belongs in files, history, or issues.

## Tools are prompts first

Most tools are a short versioned prompt plus a few kilobytes of starter code, rebuilt by
whatever AI assistant the target environment allows. Text travels through any channel, is
quick for a security team to review, and adapts to the local environment.

## Inbound is public, outbound is sanctioned

Reading from this repo is like reading documentation. Feedback from another environment
goes out only through channels that environment approves (email or chat to an own-company
address), never by posting it here from that environment. Managed accounts cannot open
issues on public repos anyway; issues are filed from this machine.
