/**
 * AURA local cookie authentication (device-local / demo grade).
 *
 * This project has no auth backend, so both the account list and the session live in
 * browser cookies written by this module:
 *
 *   aura_users    base64url JSON array of `{ u, n, s, h, a, c }` account records
 *   aura_session  base64url JSON payload + "." + signature (signed with the record hash)
 *
 * Both cookies are `path=/`, `SameSite=Lax`, and `Secure` whenever the page is served over
 * https. `aura_users` persists for a year; `aura_session` is a session cookie by default and
 * becomes a 7-day persistent cookie when "remember me" is checked.
 *
 * ⚠ Honest security note: everything below runs in the browser, so the cookie contents are
 * readable and editable from devtools. Passwords are salted and iterated-hashed (Web Crypto
 * SHA-256 when the context is secure, a JS fallback hash otherwise) so they are never stored
 * in plain text and the session signature rejects casually tampered cookies — but this is a
 * UX gate for a class project, not a security boundary. Never sign up with a real password.
 */

const USERS_COOKIE = 'aura_users';
const SESSION_COOKIE = 'aura_session';
const ACCOUNT_TTL_DAYS = 365;
const HASH_ROUNDS = 24;
const MAX_ACCOUNT_STORE_CHARS = 3800; // stay well under the ~4KB per-cookie browser limit

// Not a secret — it only keeps identical passwords from producing identical hashes.
const PEPPER = 'aura-japandi-cookie-v1';

export const SESSION_TTL_DAYS = 7;
export const AUTH_COOKIE_NAMES = { users: USERS_COOKIE, session: SESSION_COOKIE };

/* ------------------------------------------------------------------ cookie plumbing */

function readCookie(name) {
  if (typeof document === 'undefined' || !document.cookie) return null;
  const prefix = `${name}=`;
  const hit = document.cookie.split('; ').find((entry) => entry.startsWith(prefix));
  return hit ? decodeURIComponent(hit.slice(prefix.length)) : null;
}

function writeCookie(name, value, { days = 0 } = {}) {
  if (typeof document === 'undefined') return;
  const secure = typeof location !== 'undefined' && location.protocol === 'https:';
  let cookie = `${name}=${encodeURIComponent(value)}; path=/; SameSite=Lax`;
  if (secure) cookie += '; Secure';
  if (days > 0) cookie += `; Max-Age=${Math.round(days * 86400)}`;
  document.cookie = cookie;
}

function clearCookie(name) {
  if (typeof document === 'undefined') return;
  document.cookie = `${name}=; path=/; Max-Age=0; SameSite=Lax`;
}

/* ------------------------------------------------------- base64url JSON + hashing utils */

function encodePayload(value) {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function decodePayload(token) {
  const normalized = token.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
  const binary = atob(padded);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes));
}

/** Synchronous 53-bit hash — used for the session signature and as the non-secure fallback. */
function cyrb53Hex(text, seed = 0) {
  let h1 = 0xdeadbeef ^ seed;
  let h2 = 0x41c6ce57 ^ seed;
  for (let i = 0; i < text.length; i++) {
    const ch = text.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (h2 >>> 0).toString(16).padStart(8, '0') + (h1 >>> 0).toString(16).padStart(8, '0');
}

function hasSecureHashing() {
  return typeof crypto !== 'undefined' && Boolean(crypto.subtle) && typeof crypto.subtle.digest === 'function';
}

async function sha256Hex(text) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** Salted + iterated hash. `algo` is stored with the account so verification matches. */
async function hashPassword(password, salt) {
  const algo = hasSecureHashing() ? 'sha256' : 'cyrb53';
  let acc = `${PEPPER}|${salt}|${password}`;
  for (let round = 0; round < HASH_ROUNDS; round++) {
    acc = algo === 'sha256' ? await sha256Hex(`${acc}|${round}`) : cyrb53Hex(`${acc}|${round}`);
  }
  return { algo, hash: acc };
}

async function matchesPassword(password, record) {
  let acc = `${PEPPER}|${record.s}|${password}`;
  for (let round = 0; round < HASH_ROUNDS; round++) {
    acc = record.a === 'sha256' ? await sha256Hex(`${acc}|${round}`) : cyrb53Hex(`${acc}|${round}`);
  }
  return acc === record.h;
}

function randomSalt() {
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    return Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
  }
  return `${Date.now().toString(16)}${Math.random().toString(16).slice(2, 12)}`;
}

/* ---------------------------------------------------------------- account + session store */

function readAccounts() {
  const raw = readCookie(USERS_COOKIE);
  if (!raw) return [];
  try {
    const list = decodePayload(raw);
    return Array.isArray(list) ? list.filter((entry) => entry && entry.u) : [];
  } catch {
    return [];
  }
}

function writeAccounts(accounts) {
  const encoded = encodePayload(accounts);
  if (encoded.length > MAX_ACCOUNT_STORE_CHARS) {
    throw new Error('Local account storage is full on this device. Sign in with an existing account or clear the stored accounts.');
  }
  writeCookie(USERS_COOKIE, encoded, { days: ACCOUNT_TTL_DAYS });
}

function sessionSignature(payload, record) {
  return cyrb53Hex(`${payload.u}|${payload.iat}|${payload.exp}|${record.h}|${PEPPER}`);
}

function toSession(payload) {
  return {
    username: payload.u,
    name: payload.n,
    issuedAt: payload.iat,
    expiresAt: payload.exp,
    remember: Boolean(payload.r),
  };
}

function openSession(record, remember) {
  const now = Date.now();
  const payload = {
    u: record.u,
    n: record.n,
    iat: now,
    exp: now + SESSION_TTL_DAYS * 86400000,
    r: Boolean(remember),
  };
  const token = `${encodePayload(payload)}.${sessionSignature(payload, record)}`;
  // remember-me → persistent cookie, otherwise a browser-session cookie.
  writeCookie(SESSION_COOKIE, token, { days: remember ? SESSION_TTL_DAYS : 0 });
  return toSession(payload);
}

/* ------------------------------------------------------------------------- public API */

/** Reads and verifies the session cookie. Returns `null` (and clears the cookie) if invalid. */
export function getSession() {
  const raw = readCookie(SESSION_COOKIE);
  if (!raw) return null;

  const [token, signature] = raw.split('.');
  if (!token || !signature) {
    clearCookie(SESSION_COOKIE);
    return null;
  }

  let payload;
  try {
    payload = decodePayload(token);
  } catch {
    clearCookie(SESSION_COOKIE);
    return null;
  }

  const record = readAccounts().find((entry) => entry.u === payload?.u);
  const expired = !(Number(payload?.exp) > Date.now());
  const tampered = !record || signature !== sessionSignature(payload, record);
  if (tampered || expired) {
    clearCookie(SESSION_COOKIE);
    return null;
  }
  return toSession(payload);
}

export function isAuthenticated() {
  return getSession() !== null;
}

export function signOut() {
  clearCookie(SESSION_COOKIE);
}

/** Account chips shown on the auth page (never exposes salts or hashes). */
export function listLocalAccounts() {
  return readAccounts()
    .map(({ u, n, c }) => ({ username: u, name: n, createdAt: c }))
    .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));
}

export function forgetAllAccounts() {
  clearCookie(SESSION_COOKIE);
  clearCookie(USERS_COOKIE);
}

export function validateUsername(value) {
  const username = (value || '').trim();
  if (!username) return 'Choose a username.';
  if (username.length < 3 || username.length > 24) return 'Username must be 3–24 characters.';
  if (!/^[a-zA-Z0-9._-]+$/.test(username)) return 'Use only letters, numbers, dot, dash or underscore.';
  return null;
}

export function validatePassword(value) {
  const password = value || '';
  if (!password) return 'Choose a password.';
  if (password.length < 8) return 'Password must be at least 8 characters.';
  if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) return 'Mix at least one letter and one number.';
  return null;
}

/** Creates a device-local account and signs it in. Resolves with the session object. */
export async function signUp({ name, username, password, confirmPassword, remember = false }) {
  const displayName = (name || '').trim();
  const usernameError = validateUsername(username);
  if (usernameError) throw new Error(usernameError);
  const passwordError = validatePassword(password);
  if (passwordError) throw new Error(passwordError);
  if (password !== confirmPassword) throw new Error('Both passwords must match.');
  if (displayName.length < 2) throw new Error('Add the name you want shown inside the workspace.');

  const key = username.trim().toLowerCase();
  const accounts = readAccounts();
  if (accounts.some((entry) => entry.u === key)) {
    throw new Error('That username is already registered on this device — sign in instead.');
  }

  const salt = randomSalt();
  const { algo, hash } = await hashPassword(password, salt);
  const record = { u: key, n: displayName, s: salt, h: hash, a: algo, c: Date.now() };
  writeAccounts([...accounts, record]);
  return openSession(record, remember);
}

/** Verifies credentials against the local account list and signs in. */
export async function signIn({ username, password, remember = false }) {
  const key = (username || '').trim().toLowerCase();
  if (!key) throw new Error('Enter your username.');
  if (!password) throw new Error('Enter your password.');

  const record = readAccounts().find((entry) => entry.u === key);
  if (!record) throw new Error('No local account for that username — create one first.');
  if (record.a === 'sha256' && !hasSecureHashing()) {
    throw new Error('This account was created in a secure context. Re-open AURA on https:// or localhost to sign in.');
  }

  const valid = await matchesPassword(password, record);
  if (!valid) throw new Error('Incorrect password for that username.');
  return openSession(record, remember);
}
