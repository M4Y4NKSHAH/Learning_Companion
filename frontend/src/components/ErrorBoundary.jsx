import React from 'react';
import { AlertCircle, RotateCcw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Uncaught application error:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-sand-950 text-sand-50 flex flex-col items-center justify-center p-6 text-center">
          <div className="max-w-md w-full glass-panel p-8 rounded-3xl border border-clay-500/30 space-y-4 shadow-2xl">
            <div className="w-12 h-12 rounded-2xl bg-clay-500/20 text-clay-400 flex items-center justify-center mx-auto border border-clay-500/30">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold text-sand-50">Application Render Notice</h2>
            <p className="text-xs text-sand-400 leading-relaxed">
              A temporary render interruption was caught. You can reload the workspace cleanly.
            </p>
            {this.state.error && (
              <div className="bg-sand-950 p-3 rounded-xl border border-sand-900 text-[10px] font-mono text-clay-300 text-left overflow-x-auto">
                {this.state.error.toString()}
              </div>
            )}
            <button
              onClick={this.handleReset}
              className="w-full py-2.5 bg-gradient-to-r from-clay-600 to-ember-600 text-white text-xs font-bold rounded-xl shadow-lg transition flex items-center justify-center gap-2"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reload Workspace</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
