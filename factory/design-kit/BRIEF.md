# Visual direction for the wallet interface

This brief is visual direction from the product owner. The written requirements always win:
if anything here conflicts with a requirement, a required element, a required state or an
accessibility rule, follow the requirement and note the conflict in the room.

The reference screenshots in `reference/` show a consumer website whose craft we admire:
confident type, rounded colour panels, sticker details, a short branded intro and motion
with personality. Take the design language, never the material. Do not copy its code, its
fonts, its name, its logo, its illustrations or its words. Everything you ship is written by
you and bundled with the service.

## Character

Friendly and bold on the outside, calm and exact where money is shown. Think of a well-made
consumer finance app that is fun to open: big confident headings, warm colour, one playful
detail per screen, and then numbers, forms and statuses that are quiet, aligned and
unmistakable. Playfulness lives in headings, empty states, success moments and the intro.
It never touches an amount, a status or an error.

## Type

Bundle all fonts as files served by the service (no outside requests at run time). Use
open-licensed fonts only, for example from the Google Fonts catalogue under the SIL Open
Font License, and include the licence file next to the fonts.

- Display: Bricolage Grotesque, weight 800, tight tracking (about -0.02em), line height about
  0.85 to 0.95 for large headings. Used for page titles, the brand word and big moments.
- Text and controls: Figtree, weights 500, 600 and 700.
- Handwritten accent: Caveat, used sparingly for one short annotation per screen at most
  (for example a scribbled note beside an empty state). Never for information the user needs.
- Money: use tabular figures (`font-variant-numeric: tabular-nums`) for every amount so
  columns align and values do not jump when they change.

Scale (desktop / phone): hero 96 / 48 px, page title 56 / 36, section 30 / 24, body 18 / 16,
small 14. The available balance is the largest number on the page.

## Colour

Warm cream page, saturated panels, deep indigo ink. Check every text and control pair for
WCAG AA contrast; adjust tints, never the rule.

- Ink: indigo `#2B2270` for text on light panels, near-black `#0B0B0F` for body text.
- Page: cream `#FFF8E7`.
- Panels: sunflower `#FFD24A`, butter `#FAED8F`, aqua `#A4F6F8`, pink tint `#FFDBFD`,
  indigo `#3B308F` (with white text) for the footer and the intro.
- Primary action: indigo `#3B308F` with white text. Secondary: white with an indigo 2 px
  border. The one loud accent is hot pink `#FF3D9A`, for brand moments and highlights only,
  not for primary actions and never for errors.
- States, each with an icon or label so colour is never the only signal:
  available = deep green `#0E7A4B`, held = amber `#B36B00` on a light amber chip,
  pending = indigo, successful = green, refused = red `#C4271B`, uncertain (outcome not
  known) = a striped or dashed indigo-grey chip with the words "not confirmed yet".

## Shape and surface

- Big rounded panels: 24 px radius on phone, 32 px on desktop, full-width colour sections
  that sit on the cream page like stacked cards.
- Controls: pill buttons (fully rounded), 48 px tall minimum, bold labels. A button can
  carry a separate square arrow chip on its right, like a ticket stub.
- Cards: 18 px radius, 2 px ink border or a white 3 px ring on coloured panels, no blurry
  drop shadows. Sticker details may be rotated 2 to 6 degrees.
- Organic background blobs drawn as inline SVG paths in two tints of the panel colour.

## Illustrations

`art/` holds six transparent 3D illustrations made for this product by the product owner
(generated images, supplied as assets): `phone-coin`, `coins`, `paper-plane`,
`split-receipt`, `hold-padlock` and `wallet`, all WebP. You may copy them into the service
and serve them as bundled static files. They are decoration: give each an empty `alt`
unless it carries meaning, and never let one replace text the user needs. Suggested use:
`phone-coin` on the sign-up and log-in panel, `paper-plane` beside the pay form and in the
success moment, `coins` on the balance panel, `split-receipt` on the split screen,
`hold-padlock` on the authorisations screen, `wallet` in empty states. Rest them at a slight
tilt like stickers. Record in the stage's run document that these images were supplied by
the product owner, not made by the band.

## Screens

- Sign-up and log-in: the one place for marketing flair. A split layout on desktop: a colour
  panel with a large display heading, organic blobs, three or four tilted pill "stickers"
  naming benefits (see `reference/desktop-013.0.jpg`) and a short row of tilted step cards
  explaining how it works (see `reference/desktop-009.5.jpg`); the form sits on a white card
  on the other side. Stacked on phone with the form first.
- Home: the available balance as the hero number on a sunflower panel with held and total
  as quiet secondary figures below it; pay and request forms as two clear cards; the
  activity feed as a scannable list with avatar initials, direction arrow, amount coloured
  by direction, privacy shown as a small icon and label, and people-first timestamps
  ("2 min ago", full date on hover or focus).
- Requests: incoming and outgoing as two clearly labelled groups; each row shows who, how
  much, what for, and a status chip; actions are buttons on the row.
- Split: a form that shows each person's share live as the user types, and the total that
  must match.
- Authorisations: holds as cards with the reserved amount, what remains, status and actions.
- Every screen: the same top bar with the brand word, navigation to every required screen,
  and the signed-in person's name; a consistent footer.
- Placeholders never look like real data: no real handles, names or amounts as input
  examples (write "their handle" or "0.00", not a user's name).
- Times: relative for recent events ("2 min ago"), a date in words for older ones
  ("12 Sep, 14:05"); the exact timestamp only on hover or focus, never as the visible text.
- Empty states: an illustration or blob shape, one friendly display line, one helpful line
  of text and the action that fills the list.
- Loading: skeleton rows with a slow shimmer in the page colours, never a bare spinner on
  its own.

## Motion

Motion gives personality; it must never cost correctness, speed or access.

The personality comes from a handful of rules. Two tempos: springy for objects, crisp for
interface. Two easing curves: "snap" `cubic-bezier(0.32, 0.72, 0, 1)` for interface moves
(200 to 400 ms) and "glide" `cubic-bezier(0.625, 0.05, 0, 1)` as the default for everything
else; springs with light overshoot for stickers only.

- Intro: a branded intro of at most 700 ms on first load in a browser session: a fat,
  rounded brush-stroke shape in indigo sweeps across a sunflower field while the round brand
  mark pops in and out, then the stroke peels away along its own path to reveal the page.
  The real page is fully rendered and usable underneath from the first frame; the intro
  layer ignores pointer events and is removed from the DOM when it ends.
- Headlines stretch rather than fade: each word starts squashed (about 10% height, 85%
  width, shifted right and tilted about 8 degrees, pinned at its top-left corner), becomes
  opaque almost at once, then springs to full size; words start about 60 to 90 ms apart.
  Keep the heading's full text available to assistive technology as one string.
- Handwritten notes write themselves letter by letter (each letter from a small tilt, about
  15 ms apart).
- Stickers (benefit pills, step cards, badges, success confirmations) arrive like a sticker
  being slapped on: from about 90% size and a tilt, springing to a resting angle that is
  deliberately not straight (2 to 11 degrees).
- Small labels settle down into place; large objects rise up into place.
- Buttons: a springy press (scale 0.97 on press, back with overshoot) and an arrow chip that
  nudges on hover. On devices with a fine pointer, the label may do a quick squash on hover,
  animated on a wrapper so the label stays one text node.
- New feed items and successful actions: a "plop in" (scale from 0.9 with overshoot, 250 to
  350 ms) and a brief tint of the changed number. A successful payment triggers a short
  burst of about 20 small brand shapes from the button (transform only, hidden from
  assistive technology, removed when done).
- Ambient life is slow: background blobs may breathe on a 6 s loop, paused when off screen
  or when the tab is hidden.
- Panels: gentle parallax or a slight rise as they enter the viewport on the home screen.
- Page changes: use the browser's cross-document view transitions for a quick cross-fade
  where supported; never intercept normal navigation.
- Respect `prefers-reduced-motion`: no intro, no parallax, no bursts; state changes still
  show instantly.

Rules that protect behaviour (follow exactly):
1. Every required element is present, visible and clickable as soon as its data is ready.
   Nothing required starts at opacity 0 or waits for scrolling to appear.
2. No layer ever covers controls while it animates in a way that intercepts clicks.
3. No smooth-scroll library and no script that replaces page navigation.
4. Animations use transform and opacity only, and no animation may delay a network request,
   a form submission or a displayed result.
5. Numbers shown in required elements are always the final value, never an animated count.
6. All animation code and libraries are bundled with the service; plain CSS and small
   hand-written scripts are preferred over large libraries.
7. The interface behaves the same for every visitor. Never detect automation, test tools or
   particular clients to change behaviour; make every effect safe for everyone instead.
8. No native alert, confirm or prompt dialogs, no loops that keep running while nothing is
   visible, and no effect that moves a control while the pointer is over it.

## Evidence

Before handing off, capture every required screen in a real browser at 375 px and at
1440 px, in its empty, filled, loading, refused and uncertain states where they exist, and
save the images in the verification area. Check contrast and keyboard focus on each.
