#!/usr/bin/env node
/**
 * Content guard for the organisation profile. The profile is public-facing: no people's names,
 * no internal circumstances, no vendor or infrastructure names, no unannounced products.
 *
 * Checks, whole word and case-insensitive:
 *   - profile/README.md, all of it (text, alt text, links);
 *   - every SVG in profile/assets: <text>, <tspan>, <title> and <desc> content, and comments;
 *   - the file names under profile/;
 *   - every single-line string literal in scripts/build_art.py. The artwork's copy is outlined into
 *     paths there, so the SVGs hold no readable text; the words exist only as strings in that script.
 *     Docstrings are skipped (they describe how the script works, not what the artwork says).
 *
 * The terms are stored as SHA-256 digests of their lowercased words, so this public file does not
 * itself publish the words it keeps out. That is tidiness, not secrecy: anyone can hash a guess.
 * Add a term with:
 *   node -e "console.log(require('crypto').createHash('sha256').update('two words').digest('hex').slice(0, 24))"
 * Phrases of up to three words are supported.
 *
 * Exits 1 and lists every hit when anything matches; exits 0 otherwise.
 *
 *   node scripts/check-content.mjs
 */
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const PROFILE = path.join(ROOT, 'profile')

const BANNED = new Set([
  '8c8fa4a3a87d5b6ea644f306',
  'f62d8d102d4e2b84d995ce99',
  'b26d28f46ceba1518fad6a71',
  'ef7d74898c22a4bf0be437d3',
  '8dc717aadf2453897b6ba20a',
  '68fc6739afe0de142bfe3f0e',
  '56452bcadb4b215b59681bb7',
  '548d48eaddc88a03ebfa45c5',
  '7f2fe580edb35154041fa3d4',
  'c0b0109d9439de57fe3cf03a',
  '9d3508a8484ee2520ca5fe0e',
  '618b8c8de24c7b03f7a150fa',
  '887270d0cbc560af35f1326d',
  'cfe062be1bbee227d288296c',
  '1b6405d1ef5a816105210b20',
  'c857d09db23e6822e3600bc0',
  '343ab969124834fd76648a8d',
  '03507a7b702a05bbf65b8df4',
  '356e88d842568b5916bbcdc3',
  '13291c08152247c4776a7cde',
  '14648fa536d60d2ee41f4f58',
])

/** Exact strings that may contain a banned word: the Sightline address and the website address. */
const ALLOWED = ['https://sightline.dataage.co.zw', 'developersarmy.vercel.app']
/** Extra exact strings allowed in the generator only: the CSS easing function linear(), not a name. */
const ALLOWED_IN_GENERATOR = ['linear(']

const MAX_WORDS = 3
const digest = (s) => createHash('sha256').update(s).digest('hex').slice(0, 24)

function scan(where, text, allowedExtra = []) {
  let clean = text
  for (const allowed of [...ALLOWED, ...allowedExtra]) clean = clean.split(allowed).join(' ')
  const words = clean.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean)
  const hits = []
  for (let n = 1; n <= MAX_WORDS; n++) {
    for (let i = 0; i + n <= words.length; i++) {
      const phrase = words.slice(i, i + n).join(' ')
      if (BANNED.has(digest(phrase))) hits.push(`${where}: "${phrase}"`)
    }
  }
  return hits
}

/** The parts of an SVG a person can read: text, title, desc and comments. Styles and paths are skipped. */
function svgReadable(svg) {
  const parts = []
  for (const m of svg.matchAll(/<(text|tspan|title|desc)\b[^>]*>([\s\S]*?)<\/\1>/g)) parts.push(m[2].replace(/<[^>]+>/g, ' '))
  for (const m of svg.matchAll(/<!--([\s\S]*?)-->/g)) parts.push(m[1])
  return parts.join('\n')
}

/**
 * Single-line string literals in a Python file, f-strings included (their {placeholders} come along,
 * which is harmless). Triple-quoted strings are consumed first so docstrings are skipped, and comments
 * are dropped so an apostrophe in a comment can't open a fake string.
 */
function pythonStrings(source) {
  const out = []
  const token = /"""[\s\S]*?"""|'''[\s\S]*?'''|#[^\n]*|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'/g
  for (const m of source.matchAll(token)) {
    const t = m[0]
    if (t.startsWith('#') || t.startsWith('"""') || t.startsWith("'''")) continue
    out.push(t.slice(1, -1))
  }
  return out
}

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name)
    return e.isDirectory() ? [full, ...walk(full)] : [full]
  })
}

const hits = []
const readme = path.join(PROFILE, 'README.md')
hits.push(...scan('profile/README.md', readFileSync(readme, 'utf8')))

const generator = path.join(ROOT, 'scripts', 'build_art.py')
const strings = pythonStrings(readFileSync(generator, 'utf8'))
hits.push(...scan('scripts/build_art.py (strings)', strings.join('\n'), ALLOWED_IN_GENERATOR))

const files = walk(PROFILE)
for (const file of files) {
  const rel = path.relative(ROOT, file).split(path.sep).join('/')
  hits.push(...scan(`${rel} (file name)`, path.basename(file)))
  if (file.endsWith('.svg')) hits.push(...scan(rel, svgReadable(readFileSync(file, 'utf8'))))
}

if (hits.length) {
  console.error(`Content guard: ${hits.length} hit(s). The profile must stay public-facing.`)
  for (const h of hits) console.error(`  ${h}`)
  process.exit(1)
}
console.log(
  `Content guard: clean (README, ${files.filter((f) => f.endsWith('.svg')).length} SVGs and ${strings.length} generator strings checked).`,
)
