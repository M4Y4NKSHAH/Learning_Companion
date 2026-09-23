import React, { useState, useEffect } from 'react';
import { LogIn, User, Lock, Eye, EyeOff, X, AlertCircle } from 'lucide-react';
import { signIn, signUp, listLocalAccounts, validateUsername, validatePassword } from '../lib/auth';

export default function AuthModal({ isOpen, onClose, onAuthenticated, initialMode }) {
  const [mode, setMode] = useState(initialMode || 'sign-in');
  const [name, setName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [accounts, setAccounts] = useState([]);

  useEffect(() => { setAccounts(listLocalAccounts()); }, []);
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  useEffect(() => {
    setError(''); setUsername(''); setPassword('');
    setConfirmPassword(''); setName(''); setMode(initialMode || 'sign-in');
  }, [isOpen, initialMode]);

  const fieldErr = (fn, v) => { try { return fn(v) || ''; } catch { return ''; } };
  const usernameError = fieldErr(validateUsername, username);
  const passwordError = fieldErr(validatePassword, password);
  const nameError = name.trim().length < 2 && name.trim().length > 0 ? 'Add the name you want shown inside the workspace.' : '';
  const confirmError = mode === 'sign-up' && confirmPassword && password !== confirmPassword ? 'Both passwords must match.' : '';
  const submitDisabled = submitting || !!usernameError || !!passwordError || (mode === 'sign-up' && !!confirmError) || (mode === 'sign-up' && !name.trim());

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setError('');
    try {
      setSubmitting(true);
      let session;
      if (mode === 'sign-up') {
        session = await signUp({ name, username, password, confirmPassword, remember });
      } else {
        session = await signIn({ username, password, remember });
      }
      onAuthenticated?.(session);
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };
  const useExistingAccount = (entry) => { setUsername(entry.username); setPassword(''); setError(''); };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 sm:p-6 bg-sand-50/75 backdrop-blur-sm animate-fadeIn overflow-y-auto"
      onClick={() => { setError(''); onClose(); }}
    >
      <div
        className="relative w-full max-w-sm my-8 p-8 sm:p-9 glass-panel border border-sand-800 rounded-3xl shadow-japandi-lg animate-fadeInUp max-h-[92vh] overflow-y-auto custom-scrollbar"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-7">
          <div className="flex items-center gap-3">
            <div className="bg-gradient-to-tr from-ember-600 to-clay-600 p-2 rounded-xl shadow-lg shadow-sand-300/25">
              {mode === 'sign-in' ? (
                <LogIn className="w-4 h-4 text-white" />
              ) : (
                <User className="w-4 h-4 text-white" />
              )}
            </div>
            <h2 className="text-lg font-bold tracking-tight bg-gradient-to-r from-sand-50 to-sand-400 bg-clip-text text-transparent">
              {mode === 'sign-in' ? 'AURA - Sign In' : 'AURA - Create Account'}
            </h2>
          </div>
          <button
            type="button"
            onClick={() => { setError(''); onClose(); }}
            className="p-2 rounded-xl border border-sand-800 bg-sand-900/60 text-sand-400 hover:text-sand-50 hover:border-sand-600 transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex bg-sand-900/60 rounded-xl p-1 border border-sand-800 mb-7">
          <button
            type="button"
            onClick={() => { setMode('sign-in'); setError(''); }}
            className={`flex-1 text-xs font-semibold py-2 rounded-lg transition-all ${mode === 'sign-in' ? 'bg-sand-100 text-sand-950 shadow' : 'text-sand-400 hover:text-sand-200'}`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setMode('sign-up'); setError(''); }}
            className={`flex-1 text-xs font-semibold py-2 rounded-lg transition-all ${mode === 'sign-up' ? 'bg-sand-100 text-sand-950 shadow' : 'text-sand-400 hover:text-sand-200'}`}
          >
            Sign Up
          </button>
        </div>

        {error && (
          <div className="mb-5 p-3 rounded-xl bg-clay-500/10 border border-clay-500/30 text-clay-200 text-xs leading-relaxed flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-clay-400" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {mode === 'sign-up' && (
            <div>
              <label className="block text-xs font-medium text-sand-400 mb-2">Display Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ada Lovelace"
                className="w-full bg-sand-950 border border-sand-800 rounded-xl px-3.5 py-2.5 text-sm text-sand-50 placeholder-sand-500 focus:border-ember-500 focus:outline-none focus:ring-1 focus:ring-ember-500/40 transition-colors"
                required
              />
              {nameError && <p className="mt-1.5 text-[11px] text-clay-400">{nameError}</p>}
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-sand-400 mb-2">Username</label>
            <div className="relative">
              <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-sand-500" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="your_name"
                className="w-full bg-sand-950 border border-sand-800 rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-sand-50 placeholder-sand-500 focus:border-ember-500 focus:outline-none focus:ring-1 focus:ring-ember-500/40 transition-colors"
                required
              />
            </div>
            {usernameError && <p className="mt-1.5 text-[11px] text-clay-400">{usernameError}</p>}
          </div>

          <div>
            <label className="block text-xs font-medium text-sand-400 mb-2">Password</label>
            <div className="relative">
              <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-sand-500" />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-sand-950 border border-sand-800 rounded-xl pl-10 pr-10 py-2.5 text-sm text-sand-50 placeholder-sand-500 focus:border-ember-500 focus:outline-none focus:ring-1 focus:ring-ember-500/40 transition-colors"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-lg text-sand-500 hover:text-sand-200 hover:bg-sand-900 transition-colors"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {passwordError && <p className="mt-1.5 text-[11px] text-clay-400">{passwordError}</p>}
          </div>


          {mode === 'sign-up' && (
            <div>
              <label className="block text-xs font-medium text-sand-400 mb-2">Confirm Password</label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-sand-500" />
                <input
                  type={showConfirm ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-sand-950 border border-sand-800 rounded-xl pl-10 pr-10 py-2.5 text-sm text-sand-50 placeholder-sand-500 focus:border-ember-500 focus:outline-none focus:ring-1 focus:ring-ember-500/40 transition-colors"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-lg text-sand-500 hover:text-sand-200 hover:bg-sand-900 transition-colors"
                  aria-label={showConfirm ? 'Hide password' : 'Show password'}
                >
                  {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {confirmError && <p className="mt-1.5 text-[11px] text-clay-400">{confirmError}</p>}
            </div>

          )}
          <div className="flex items-center justify-between pt-0.5">
            <label className="flex items-center gap-2 text-xs text-sand-400 cursor-pointer">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="w-3.5 h-3.5 rounded border border-sand-600 bg-sand-950 text-ember-500 focus:ring-ember-500/40"
              />
              <span>Remember me</span>
            </label>
            {mode === 'sign-in' && (
              <button
                type="button"
                onClick={() => signOut()}
                className="text-[11px] text-sand-400 hover:text-sand-50 underline underline-offset-2 transition-colors"
              >
                Clear session
              </button>
            )}
          </div>
          )}

          <button
            type="submit"
            disabled={submitDisabled}
            className="w-full bg-ember-600 hover:bg-ember-500 disabled:opacity-50 disabled:pointer-events-none text-white text-sm font-bold py-3 rounded-xl shadow-lg shadow-sand-300/25 transition-all flex items-center justify-center gap-2 active:scale-[0.98]"
          >
            {submitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>{mode === 'sign-up' ? 'Creating account…' : 'Signing in…'}</span>
              </>
            ) : (
              <>{mode === 'sign-up' ? 'Create Account' : 'Sign In'}</>
            )}
          </button>
        </form>

        {/* Dev convenience: pick a locally-stored account */}
        {mode === 'sign-in' && accounts.length > 0 && (
          <div className="mt-6 pt-5 border-t border-sand-800">
            <p className="text-[10px] text-sand-500 uppercase font-semibold tracking-wider mb-2.5">
              Local accounts on this device
            </p>
            <div className="space-y-2">
              {accounts.map((entry) => (
                <button
                  key={entry.username}
                  type="button"
                  onClick={() => useExistingAccount(entry)}
                  className="w-full text-left px-3 py-2.5 rounded-xl border border-sand-800 bg-sand-900/40 hover:bg-sand-900 text-xs text-sand-300 hover:text-sand-50 transition-colors"
                >
                  <span className="font-medium">{entry.username}</span>
                  {entry.name && <span className="text-sand-500"> — {entry.name}</span>}
                </button>
              ))}
            </div>
          </div>
        )}

        <p className="mt-6 text-[10px] text-sand-500 text-center leading-relaxed">
          Accounts are stored <strong>device-locally</strong> in cookies. Demo gate for a
          class project — never sign up with a real password.
        </p>
      </div>
    </div>
  );
}