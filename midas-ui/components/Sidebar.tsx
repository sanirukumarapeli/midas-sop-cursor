"use client";

import React, { useState } from "react";
import { Factory, Zap, TrendingUp, ShieldCheck, Settings, RefreshCw, Brain, Rocket, Loader2 } from "lucide-react";

export default function Sidebar() {
  const [isRetraining, setIsRetraining] = useState(false);
  const [retrainStatus, setRetrainStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const handleReset = async () => {
    try {
      const response = await fetch("http://127.0.0.1:8000/api/reset", {
        method: "POST",
      });

      if (!response.ok) {
        console.error("Warning: Backend failed to confirm memory wipe.");
      }

      window.dispatchEvent(new Event('clearChatHistory'));

    } catch (error) {
      console.error("Network error while trying to reset backend memory:", error);
      window.dispatchEvent(new Event('clearChatHistory'));
    }
  };

  const handleRetrain = async () => {
    setIsRetraining(true);
    setRetrainStatus(null);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/retrain", {
        method: "POST",
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Server error occurred during retraining.");
      }

      setRetrainStatus({ type: "success", message: "✅ Models retrained successfully!" });
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : "An unknown error occurred.";
      setRetrainStatus({ type: "error", message: `❌ ${errorMessage}` });
    } finally {
      setIsRetraining(false);
      setTimeout(() => setRetrainStatus(null), 6000);
    }
  };

  return (
    <div className="w-72 h-full bg-[#141414] border-r border-zinc-800/80 flex flex-col text-zinc-400 shrink-0 overflow-y-auto hidden md:flex">
      <div className="p-6">
        <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2">
          <Factory className="w-5 h-5 text-zinc-500" strokeWidth={1.5} />
          S&OP Control Tower
        </h2>
      </div>

      <hr className="border-zinc-800/80 mx-6 mb-6" />

      <div className="px-6 space-y-3 flex-1">
        <h3 className="text-sm font-medium text-zinc-300 mb-4">System Status</h3>

        <StatusBadge icon={Zap} text="Intelligent S&OP Co-Pilot: Active" />
        <StatusBadge icon={TrendingUp} text="Demand Forecasting Module: Live" />
        <StatusBadge icon={ShieldCheck} text="Fulfillment Reliability Engine: Operational" />
        <StatusBadge icon={Settings} text="Network Optimization Engine: Linked" />

        <hr className="border-zinc-800/80 my-6" />

        <button
          onClick={handleReset}
          disabled={isRetraining}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-zinc-700/80 rounded-xl text-sm text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200 hover:border-zinc-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw className="w-4 h-4 text-zinc-500" strokeWidth={1.5} />
          Reset Copilot Analytics
        </button>

        <hr className="border-zinc-800/80 my-6" />

        <h3 className="text-sm font-medium text-zinc-300 mb-4 flex items-center gap-2">
          <Brain className="w-5 h-5 text-zinc-500" strokeWidth={1.5} />
          ML Admin Controls
        </h3>

        <div className="space-y-3">
          <button
            onClick={handleRetrain}
            disabled={isRetraining}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-zinc-700/80 rounded-xl text-sm text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200 hover:border-zinc-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isRetraining ? (
              <>
                <Loader2 className="w-4 h-4 text-orange-400/80 animate-spin" strokeWidth={1.5} />
                Retraining Models...
              </>
            ) : (
              <>
                <Rocket className="w-4 h-4 text-orange-400/80" strokeWidth={1.5} />
                Retrain Models (Live DB)
              </>
            )}
          </button>

          {retrainStatus && (
            <div className={`p-3 rounded-xl text-xs border leading-relaxed ${retrainStatus.type === 'success' ? 'bg-emerald-950/30 border-emerald-900/40 text-emerald-400' : 'bg-red-950/30 border-red-900/40 text-red-400'}`}>
              {retrainStatus.message}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ icon: Icon, text }: { icon: React.ElementType, text: string }) {
  return (
    <div className="flex items-center gap-3 bg-emerald-950/15 border border-emerald-900/40 rounded-xl p-3">
      <Icon className="w-4 h-4 text-emerald-500/90 shrink-0" strokeWidth={1.5} />
      <span className="text-[13px] font-medium text-emerald-500/90 leading-snug">{text}</span>
    </div>
  );
}
