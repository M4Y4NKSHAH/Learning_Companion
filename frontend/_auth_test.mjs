// Temporary validation harness for src/lib/auth.js — emulates document.cookie in Node.
const jar = new Map();

globalThis.document = {
  get cookie() {
    return [...jar.entries()].map(([k, v]) => `${k}=${v.value}`).join('; ');
  },
  set cookie(raw) {
    const [pair, ...attrs] = raw.split(';').map((s) => s.trim());
    const idx = pair.indexOf('=');
    const name = pair.slice(0, idx);
    const value = pair.slice(idx + 1);
    const maxAge = attrs.find((a) => /^max-age=/i.test(a));
    const dead = maxAge && Number(maxAge.split('=')[1]) <= 0;
    if (!value || dead) jar.delete(name);
    else jar.set(name, { value, attrs });
  },
};

const attrOf = (name, key) => {
  const entry = jar.get(name);
  return entry?.attrs.find((a) => a.toLowerCase().startsWith(key.toLowerCase())) ?? null;
};

const {
  signUp, signIn, signOut, getSession, isAuthenticated,
  listLocalAccounts, forgetAllAccounts, AUTH_COOKIE_NAMES, SESSION_TTL_DAYS
} = await import('./src/lib/auth.js');

let pass = 0;
let fail = 0;
const check = (label, condition, extra = '') => {
  if (condition) { pass++; console.log(`PASS  ${label}`); }
  else { fail++; console.log(`FAIL  ${label} ${extra}`); }
};
const rejects = async (label, fn, expectedFragment) => {
  try {
    await fn();
    check(label, false, '(expected a rejection)');
  } catch (error) {
    check(label, String(error.message).includes(expectedFragment), `→ got "${error.message}"`);
  }
};

const { users: USERS, session: SESSION } = AUTH_COOKIE_NAMES;

console.log(`--- hashing path: ${globalThis.crypto?.subtle ? 'sha256' : 'cyrb53 fallback'} ---`);

check('starts signed out', getSession() === null && isAuthenticated() === false);

await rejects('rejects short username', () => signUp({ name: 'Ada', username: 'ab', password: 'secret123', confirmPassword: 'secret123' }), '3–24');
await rejects('rejects bad username chars', () => signUp({ name: 'Ada', username: 'ada lovelace', password: 'secret123', confirmPassword: 'secret123' }), 'Use only letters');
await rejects('rejects short password', () => signUp({ name: 'Ada', username: 'ada_l', password: 'short', confirmPassword: 'short' }), 'at least 8');
await rejects('rejects letters-only password', () => signUp({ name: 'Ada', username: 'ada_l', password: 'passwordonly', confirmPassword: 'passwordonly' }), 'one letter and one number');
await rejects('rejects mismatched confirmation', () => signUp({ name: 'Ada', username: 'ada_l', password: 'secret123', confirmPassword: 'secret124' }), 'must match');
await rejects('rejects missing display name', () => signUp({ name: 'A', username: 'ada_l', password: 'secret123', confirmPassword: 'secret123' }), 'name you want shown');

const created = await signUp({ name: 'Ada Lovelace', username: 'ada_l', password: 'secret123', confirmPassword: 'secret123', remember: true });
check('signUp returns session', created.username === 'ada_l' && created.name === 'Ada Lovelace' && created.remember === true);
check('remember-me sets 7-day cookie', (attrOf(SESSION, 'max-age') || '').endsWith(String(SESSION_TTL_DAYS * 86400)), attrOf(SESSION, 'max-age') || 'no max-age');
check('session cookie is path=/ + SameSite=Lax', attrOf(SESSION, 'path') === 'path=/' && (attrOf(SESSION, 'samesite') || '').toLowerCase().includes('lax'));

const storedUsers = decodeURIComponent(jar.get(USERS).value);
check('account cookie stores no plaintext password', !storedUsers.includes('secret123'));
const records = JSON.parse(Buffer.from(storedUsers.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'));
check('account record is salted + hashed', records.length === 1 && records[0].s.length >= 16 && records[0].h.length >= 16 && ['sha256', 'cyrb53'].includes(records[0].a), `algo=${records[0]?.a}`);

check('session survives a reload', getSession()?.username === 'ada_l');


await rejects('rejects duplicate username', () => signUp({ name: 'Ada Two', username: 'ADA_L', password: 'secret123', confirmPassword: 'secret123' }), 'already registered');

signOut();
check('signOut clears the session cookie', getSession() === null && !jar.has(SESSION));
check('signOut keeps the stored account', jar.has(USERS));

await rejects('rejects unknown username', () => signIn({ username: 'nobody', password: 'secret123' }), 'No local account');
await rejects('rejects wrong password', () => signIn({ username: 'ada_l', password: 'secret999' }), 'Incorrect password');

const noRemember = await signIn({ username: 'ADA_L', password: 'secret123' });
check('signIn is case-insensitive', noRemember.username === 'ada_l' && noRemember.name === 'Ada Lovelace');
check('no remember-me → browser-session cookie', attrOf(SESSION, 'max-age') === null);

await signUp({ name: 'Grace Hopper', username: 'grace', password: 'cobol2024', confirmPassword: 'cobol2024', remember: true });
check('second account created and signed in', getSession()?.username === 'grace');

const listed = listLocalAccounts();
check('listLocalAccounts hides secrets', listed.length === 2 && !('h' in listed[0]) && !('s' in listed[0]), listed.map((l) => l.username).join(','));

// Tampering: flip bytes in the session payload → the signature must reject it.
const [token, signature] = decodeURIComponent(jar.get(SESSION).value).split('.');
jar.set(SESSION, { value: `${token.slice(0, -2)}XY.${signature}`, attrs: jar.get(SESSION).attrs });
check('tampered session is rejected + cleared', getSession() === null && !jar.has(SESSION));

// Expiry: jump the clock past the TTL and confirm the session dies.
await signIn({ username: 'grace', password: 'cobol2024', remember: true });
const realNow = Date.now;
Date.now = () => realNow() + (SESSION_TTL_DAYS + 1) * 86400000;
check('expired session is rejected + cleared', getSession() === null && !jar.has(SESSION));
Date.now = realNow;

// Guard the cookie-capacity failure mode (accounts piggyback on one ~4KB cookie).
let capacityMessage = '';
for (let i = 0; i < 80; i++) {
  try {
    await signUp({ name: `User ${i}`, username: `user_${i}_long_name`, password: 'secret123', confirmPassword: 'secret123' });
  } catch (error) {
    capacityMessage = String(error.message);
    break;
  }
}
check('cookie capacity guard fires with a friendly message', capacityMessage.includes('storage is full'), `→ "${capacityMessage}"`);

forgetAllAccounts();
check('forgetAllAccounts clears both cookies', !jar.has(USERS) && !jar.has(SESSION) && getSession() === null);

console.log(`\n${fail === 0 ? 'ALL GREEN' : 'FAILURES'} → ${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
