// Panicci Content Engine — proven short-form format library.
//
// Half of these are the well-documented viral-creator patterns (story, challenge,
// hook-reveal, comparison) that any format-matching tool draws on. The other half
// — tagged origin: "authority" — are Panicci's own addition: formats built for
// interview-style, on-camera expert/founder content, which is the shape this tool
// actually captures. Generic format-matchers built for solo lifestyle creators
// don't cover this ground, which is the point.
//
// Each format's `perf` block is a running average filled in over time by the
// performance feedback loop (see api/log-performance.js). Starts null until real
// data exists — never fabricate a starting number.

const FORMATS = [
  // ---------- Consumer / viral-creator patterns ----------
  {
    id: "personal-story",
    name: "The Personal Story",
    category: "Storytelling",
    origin: "consumer",
    structure: ["Cold open at the lowest point or the moment things changed", "The turn — what you realized or did differently", "The result", "Tie it back to the value you deliver now"],
    whyItWorks: "Vulnerability earns attention before the pitch starts; viewers finish because they want to know how it resolved.",
    bestTypes: ["INTRO", "NICHE"],
    hookTemplates: ["I got fired on my {age}th birthday. {turn}.", "Three years ago I almost quit {niche}. Here's what changed."]
  },
  {
    id: "would-you-rather",
    name: "Would You Rather",
    category: "Challenge",
    origin: "consumer",
    structure: ["Present two specific options tied to the niche", "Force a real trade-off, not a fake one", "Give your answer and the one-line reason why"],
    whyItWorks: "Binary choices are the lowest-friction way to get a comment — everyone has an instant opinion.",
    bestTypes: ["OU", "HOT"],
    hookTemplates: ["Would you rather {optionA} or {optionB}? Most people get this wrong."]
  },
  {
    id: "myth-bust",
    name: "Did You Know / Myth Bust",
    category: "Educational",
    origin: "consumer",
    structure: ["State the common belief", "Flatly contradict it", "Prove it in one sentence", "Give the correct move instead"],
    whyItWorks: "Correcting a misconception triggers curiosity and positions you as the authority in three seconds.",
    bestTypes: ["NICHE", "HOT"],
    hookTemplates: ["You've been doing {common task} wrong your whole life.", "Everyone thinks {belief}. Here's why that's backwards."]
  },
  {
    id: "blind-test",
    name: "Can You Tell the Difference",
    category: "Challenge",
    origin: "consumer",
    structure: ["Set up a side-by-side or blind comparison", "Reveal which is which", "Explain the tell"],
    whyItWorks: "Viewers play along and want to see if they guessed right — near-100% watch-to-reveal completion.",
    bestTypes: ["NICHE"],
    hookTemplates: ["Can you tell the difference between {A} and {B}? Loser does something silly."]
  },
  {
    id: "expensive-secret",
    name: "Expensive Secret Reveal",
    category: "Hook-Reveal",
    origin: "consumer",
    structure: ["Name a surprising price or investment", "Hold the reveal of what it actually bought", "Pay it off with the real answer"],
    whyItWorks: "A dollar figure is a pattern interrupt; the open loop (what did it buy?) carries the watch time.",
    bestTypes: ["NICHE", "HOT"],
    hookTemplates: ["My client just spent ${amount} on {thing}, and you won't believe what they got for it."]
  },
  {
    id: "first-vs-pro",
    name: "First Attempt vs Pro",
    category: "Comparison",
    origin: "consumer",
    structure: ["Show or describe the beginner version", "Show or describe the expert version", "Name the 1-2 things that separate them"],
    whyItWorks: "Side-by-side skill contrast is instantly legible and makes expertise visible instead of just claimed.",
    bestTypes: ["NICHE"],
    hookTemplates: ["First {task} vs. after {timeframe} of doing it professionally."]
  },
  {
    id: "quiz-consequences",
    name: "Quiz With Consequences",
    category: "Challenge",
    origin: "consumer",
    structure: ["Ask a specific, answerable question", "Beat/count down", "Reveal the answer with a real stake attached"],
    whyItWorks: "Adding a consequence (bet, forfeit, guess-the-number) turns passive viewers into active predictors.",
    bestTypes: ["OU", "HOT"],
    hookTemplates: ["Guess {number} or I {consequence}."]
  },
  {
    id: "before-after",
    name: "Before / After Transformation",
    category: "Comparison",
    origin: "consumer",
    structure: ["Show the starting state plainly, no exaggeration", "Cut to the result", "Name the one change that mattered most"],
    whyItWorks: "Transformation is the oldest hook in direct response for a reason — it's proof, not a promise.",
    bestTypes: ["NICHE"],
    hookTemplates: ["This is what {client/thing} looked like before we touched it."]
  },
  {
    id: "hot-take",
    name: "The Rant / Hot Take",
    category: "Opinion",
    origin: "consumer",
    structure: ["State the unpopular opinion in the first line", "Give one real reason, not five", "Land it — don't soften the ending"],
    whyItWorks: "Disagreement drives comments and shares more reliably than agreement; the algorithm rewards the debate.",
    bestTypes: ["HOT"],
    hookTemplates: ["Unpopular opinion: {spicy claim}."]
  },
  {
    id: "behind-scenes",
    name: "Day in the Life / Behind the Build",
    category: "Documentary",
    origin: "consumer",
    structure: ["Drop into the middle of real work, no intro", "Narrate one decision as it happens", "Cut before it gets slow"],
    whyItWorks: "Process footage reads as authentic in a feed full of polished pitches — it earns trust by not selling.",
    bestTypes: ["NICHE", "INTRO"],
    hookTemplates: ["Come watch me {task} — here's what actually goes into it."]
  },

  // ---------- Authority formats (Panicci's own addition — built for interview-style, on-camera expert content, not solo lifestyle creators) ----------
  {
    id: "founder-origin",
    name: "The Founder Origin Story",
    category: "Authority",
    origin: "authority",
    structure: ["Why you started — the specific frustration or gap", "The first proof it worked", "Who you built it for"],
    whyItWorks: "Buyers trust founders who can name the exact problem they set out to fix, not a generic mission statement.",
    bestTypes: ["INTRO"],
    hookTemplates: ["I started {business} because {specific frustration} — and no one was fixing it."]
  },
  {
    id: "client-result",
    name: "The Client Result Reveal",
    category: "Authority",
    origin: "authority",
    structure: ["State the client's starting problem in one line", "State the specific, numeric result", "Name the one thing you did that caused it"],
    whyItWorks: "A specific number beats a testimonial — it's evidence a prospect can picture happening to them.",
    bestTypes: ["NICHE"],
    hookTemplates: ["A client came to us with {problem}. {timeframe} later: {specific result}."]
  },
  {
    id: "myth-vs-reality",
    name: "Myth vs Reality in {industry}",
    category: "Authority",
    origin: "authority",
    structure: ["Say what most people assume about the industry", "Say what's actually true", "Explain why the gap exists"],
    whyItWorks: "Industry insiders have information asymmetry — sharing it positions you above the DIY/guesswork crowd.",
    bestTypes: ["NICHE", "HOT"],
    hookTemplates: ["What clients think {industry} costs vs. what it actually costs — and why."]
  },
  {
    id: "amaa-rapid-fire",
    name: "Ask Me Anything — Rapid Fire",
    category: "Authority",
    origin: "authority",
    structure: ["Rapid-fire 3-5 real questions clients actually ask", "One-breath answers, no hedging", "End on the most-asked one"],
    whyItWorks: "Speed reads as competence; stacking several answers in one clip gives editors more cuttable segments per shoot.",
    bestTypes: ["NICHE"],
    hookTemplates: ["The questions every client asks me in week one — answered in 60 seconds."]
  },
  {
    id: "objection-flip",
    name: "The Objection Flip",
    category: "Authority",
    origin: "authority",
    structure: ["Say the #1 reason people hesitate to buy/hire", "Agree with the concern instead of dismissing it", "Reframe why it's not actually the risk they think"],
    whyItWorks: "Naming the objection out loud disarms it — prospects trust someone who addresses doubt instead of hiding from it.",
    bestTypes: ["HOT", "NICHE"],
    hookTemplates: ["The #1 reason people don't hire a {role}? Here's why that fear is backwards."]
  },
  {
    id: "expensive-mistake",
    name: "The Expensive Mistake",
    category: "Authority",
    origin: "authority",
    structure: ["Name the mistake most people in the niche make", "Name the real cost — money, time, or risk", "Give the one-line fix"],
    whyItWorks: "Loss-aversion outperforms benefit-framing; 'avoid this' hooks harder than 'here's a tip.'",
    bestTypes: ["NICHE", "HOT"],
    hookTemplates: ["The #1 mistake {audience} makes with {topic} — and what it actually costs them."]
  },
  {
    id: "numbers-dont-lie",
    name: "Numbers Don't Lie",
    category: "Authority",
    origin: "authority",
    structure: ["Lead with one specific, surprising stat or benchmark", "Explain what it means in plain terms", "Tell the viewer what to do with that information"],
    whyItWorks: "A hard number is unskippable in a feed of opinions — it reads as researched, not just asserted.",
    bestTypes: ["NICHE", "HOT"],
    hookTemplates: ["{stat}% of {audience} lose money on this without realizing it."]
  },
  {
    id: "overrated-underrated-industry",
    name: "Overrated / Underrated (Industry Edition)",
    category: "Authority",
    origin: "authority",
    structure: ["Name one specific tool, trend, or tactic in the niche", "Call it overrated or underrated", "One sentence of proof"],
    whyItWorks: "Same comment-bait mechanic as consumer O/U, aimed at industry debates your actual audience has opinions about.",
    bestTypes: ["OU"],
    hookTemplates: ["{specific tool/trend} — overrated or underrated? My honest answer."]
  },
  {
    id: "direct-cta",
    name: "The Direct Next Step",
    category: "Authority",
    origin: "authority",
    structure: ["Restate the value delivered in this clip in one line", "Name exactly who should act", "Give the single next step"],
    whyItWorks: "A specific, singular CTA converts better than a vague 'link in bio' — clarity beats cleverness at the close.",
    bestTypes: ["CTA"],
    hookTemplates: ["If {specific situation} is you, here's exactly what to do next."]
  }
];

// A format's live performance score once real posts have been logged.
// null until api/log-performance.js has data for it — never seed a fake number.
function withPerf(perfByFormatId) {
  return FORMATS.map((f) => ({
    ...f,
    perf: (perfByFormatId && perfByFormatId[f.id]) || null
  }));
}

function byId(id) {
  return FORMATS.find((f) => f.id === id) || null;
}

function forTypes(types) {
  const wanted = new Set(types);
  return FORMATS.filter((f) => f.bestTypes.some((t) => wanted.has(t)));
}

module.exports = { FORMATS, withPerf, byId, forTypes };
