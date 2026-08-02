# Script tags

TelePrompter reads three tags out of a plain-text script. Everything else is
delivered to the glass exactly as you typed it.

## `[PAUSE]`

On a line of its own. When this line reaches the focus band the scroll stops and
the transport returns to a paused state. Press play to continue from that point.

```
And that brings us to the interview.

[PAUSE]

Thank you for joining us this evening.
```

Use it wherever you hand over to somebody else: a guest answer, a video roll, an
outside broadcast.

The tag is case-insensitive and tolerates spaces, so `[pause]` and `[ PAUSE ]`
work too. Written inside a sentence it is *not* a marker — `say [PAUSE] here`
scrolls past normally.

## `[CHAPTER Title]`

On a line of its own. Becomes a heading on the prompter, an entry in the outline
beside the editor, and a tick on the progress bar.

```
[CHAPTER Cold open]
Good evening, and welcome to the programme.

[CHAPTER The main story]
Our first report comes from the north of the country.
```

Chapters are how you navigate a long script:

- click an entry in the outline to jump there
- <kbd>Ctrl</kbd>+<kbd>←</kbd> / <kbd>Ctrl</kbd>+<kbd>→</kbd> move between them
- the active chapter is shown in the prompter's corner readout
- each chapter's real duration is recorded in the rehearsal history

A bare `[CHAPTER]` with no title is numbered automatically.

## `[[note text]]`

Anywhere inside a line. The note is removed from the prompter text and appears
only in the presenter notes window.

```
Good evening. [[wait for the music sting]]
Tonight, three stories. [[camera two]]
```

Several notes on one line are joined together. A line containing nothing but a
note becomes a blank line on the glass, so you can leave yourself instructions
without disturbing the read.

Notes are rendered as plain text. A note containing markup is shown literally,
never interpreted.

## What is not a tag

Square brackets on their own are ordinary text. `[sic]`, `[laughs]` and
`[applause]` all scroll past as written — only the three forms above are
recognised.
