/**
 * Normalize dense LLM prose into readable Markdown for Strategic Insights /
 * Recommendations before ReactMarkdown renders them.
 */

function toTitleCase(heading: string): string {
  return heading
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\b(And|Or|Of|The|A|An|For|To|In|On|&)\b/g, (w) =>
      w === "&" ? "&" : w.toLowerCase()
    )
    .replace(/^\w/, (c) => c.toUpperCase());
}

/** Split ALL-CAPS section labels like "IMMEDIATE ESCALATION REQUIRED: …" */
function splitCapsHeadings(text: string): string {
  // At least two ALL-CAPS tokens ending with a colon
  const pattern =
    /(?:^|\n\n?|\.\s+)([A-Z][A-Z0-9]*(?:\s+(?:&|[A-Z][A-Z0-9]*)){1,}:)\s*/g;

  return text
    .replace(pattern, (match, heading: string, offset: number) => {
      const title = toTitleCase(heading.slice(0, -1).trim());
      const prefix =
        offset === 0 || match.startsWith("\n")
          ? ""
          : match.startsWith(".")
            ? ".\n\n"
            : "\n\n";
      // If match includes leading ". ", keep sentence end then break
      if (/^\.\s+/.test(match)) {
        return `.\n\n**${title}**\n\n`;
      }
      return `${prefix}**${title}**\n\n`;
    })
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Rewrite (1)/(2)/(3) or (a)/(b)/(c) crammed into one paragraph into Markdown lists */
function rewriteParenEnumerations(
  block: string,
  pattern: RegExp,
  markerFor: (capture: string, index: number) => string
): string {
  const re = new RegExp(pattern.source, pattern.flags.includes("g") ? pattern.flags : `${pattern.flags}g`);
  const matches = [...block.matchAll(re)];
  if (matches.length < 2 || matches[0].index === undefined) return block;

  const parts: string[] = [];
  const intro = block.slice(0, matches[0].index).trim();
  if (intro) {
    parts.push(intro.replace(/[:：]\s*$/, ":"));
  }

  for (let i = 0; i < matches.length; i++) {
    const m = matches[i];
    const start = (m.index ?? 0) + m[0].length;
    const end = i + 1 < matches.length ? (matches[i + 1].index ?? block.length) : block.length;
    let itemBody = block.slice(start, end).trim();
    // Drop a trailing connector like "; and" / "," before the next item was split
    itemBody = itemBody.replace(/[;,]?\s*(?:and|or)?\s*$/i, "").trim();
    if (!itemBody) continue;
    // Ensure sentence capitalization
    itemBody = itemBody.charAt(0).toUpperCase() + itemBody.slice(1);
    parts.push(`${markerFor(m[1], i)} ${itemBody}`);
  }

  return parts.join("\n\n");
}

/** Split "1. foo 2. bar" jammed on one line into a real numbered list */
function expandInlineDotNumbering(block: string): string {
  if (block.includes("\n")) return block;
  const matches = [...block.matchAll(/(?:^|\s)(\d+)\.\s+/g)];
  if (matches.length < 2 || matches[0].index === undefined) return block;

  const parts: string[] = [];
  const firstIdx = matches[0].index;
  const intro = block.slice(0, firstIdx).trim();
  if (intro) parts.push(intro.replace(/[:：]\s*$/, ":"));

  for (let i = 0; i < matches.length; i++) {
    const m = matches[i];
    const start = (m.index ?? 0) + m[0].length;
    const end = i + 1 < matches.length ? (matches[i + 1].index ?? block.length) : block.length;
    let itemBody = block.slice(start, end).trim();
    itemBody = itemBody.replace(/[;,]?\s*(?:and|or)?\s*$/i, "").trim();
    if (!itemBody) continue;
    itemBody = itemBody.charAt(0).toUpperCase() + itemBody.slice(1);
    parts.push(`${m[1]}. ${itemBody}`);
  }

  return parts.join("\n\n");
}

function expandInlineEnumerations(block: string): string {
  const trimmed = block.trim();
  if (!trimmed) return "";

  // Already structured multi-line markdown list — just loosen spacing
  if (/^(\s*(\d+\.|[-*+])\s+.+\n)+/m.test(trimmed) && trimmed.includes("\n")) {
    return trimmed
      .split("\n")
      .map((line) => line.trimEnd())
      .join("\n")
      .replace(/\n(?=\s*(\d+\.|[-*+])\s)/g, "\n\n");
  }

  let result = trimmed;

  const numParen = [...result.matchAll(/\((\d+)\)\s+/g)];
  if (numParen.length >= 2) {
    result = rewriteParenEnumerations(result, /\((\d+)\)\s+/g, (n) => `${n}.`);
  }

  // Also expand lettered (a)(b)(c) — including inside numbered items
  result = result
    .split(/\n{2,}/)
    .map((part) => {
      const letterParen = [...part.matchAll(/\(([a-z])\)\s+/gi)];
      if (letterParen.length >= 2) {
        return rewriteParenEnumerations(part, /\(([a-z])\)\s+/gi, () => "-");
      }
      return expandInlineDotNumbering(part);
    })
    .join("\n\n");

  return result;
}

/**
 * Convert dense strategic_insights / recommendations text into spaced Markdown.
 */
export function formatReadableProse(raw: string | null | undefined): string {
  if (!raw || typeof raw !== "string") return "";
  let text = raw.replace(/\r\n/g, "\n").trim();
  if (!text) return "";

  text = splitCapsHeadings(text);

  text = text
    .split(/\n{2,}/)
    .map((block) => expandInlineEnumerations(block))
    .filter(Boolean)
    .join("\n\n");

  return text.replace(/\n{3,}/g, "\n\n").trim();
}
