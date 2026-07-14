"use client";

import React, { useState } from "react";
import { Factory, Zap, TrendingUp, ShieldCheck, Settings, RefreshCw, Brain, Rocket, Loader2 } from "lucide-react";

export default function Sidebar() {
  const [isRetraining, setIsRetraining] = useState(false);
  const [retrainStatus, setRetrainStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

// 🔄 Reset Copilot Analytics (Deep Core Wipe)
  const handleReset = async () => {
    try {
      // 1. Send the wipe command to the Python backend
      const response = await fetch("http://127.0.0.1:8000/api/reset", {
        method: "POST",
      });

      if (!response.ok) {
        console.error("Warning: Backend failed to confirm memory wipe.");
      }

      // 2. Dispatch the silent signal to clear the Next.js UI Chat Dashboard
      window.dispatchEvent(new Event('clearChatHistory'));

    } catch (error) {
      console.error("Network error while trying to reset backend memory:", error);
      // Even if the network fails, we still want to clear the frontend screen
      window.dispatchEvent(new Event('clearChatHistory'));
    }
  };

  // 🚀 Retrain Models (Live DB)
  const handleRetrain = async () => {
    setIsRetraining(true);
    setRetrainStatus(null);

    try {
      // Call the new FastAPI endpoint
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
      // Automatically hide the status message after 6 seconds
      setTimeout(() => setRetrainStatus(null), 6000);
    }
  };

  return (
    <div className="w-72 h-full bg-slate-950 border-r border-slate-800 flex flex-col text-slate-300 shrink-0 overflow-y-auto hidden md:flex">
      {/* Header */}
      <div className="p-6">
        <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Factory className="w-5 h-5 text-slate-400" />
          S&OP Control Tower
        </h2>
      </div>

      <hr className="border-slate-800 mx-6 mb-6" />

      {/* System Status Section */}
      <div className="px-6 space-y-3 flex-1">
        <h3 className="text-sm font-semibold text-slate-100 mb-4">System Status</h3>

        {/* Green Status Badges matching Streamlit */}
        <StatusBadge icon={Zap} text="Intelligent S&OP Co-Pilot: Active" />
        <StatusBadge icon={TrendingUp} text="Demand Forecasting Module: Live" />
        <StatusBadge icon={ShieldCheck} text="Fulfillment Reliability Engine: Operational" />
        <StatusBadge icon={Settings} text="Network Optimization Engine: Linked" />
        
        <hr className="border-slate-800 my-6" />

        {/* Action Buttons */}
        <button 
          onClick={handleReset}
          disabled={isRetraining}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-slate-700 rounded-md text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-200 hover:border-slate-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw className="w-4 h-4 text-blue-400" />
          Reset Copilot Analytics
        </button>

        <hr className="border-slate-800 my-6" />

        {/* ML Admin Controls */}
        <h3 className="text-sm font-semibold text-slate-100 mb-4 flex items-center gap-2">
          <Brain className="w-5 h-5 text-pink-400" />
          ML Admin Controls
        </h3>

        <div className="space-y-3">
          <button 
            onClick={handleRetrain}
            disabled={isRetraining}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-slate-700 rounded-md text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-200 hover:border-slate-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isRetraining ? (
              <>
                <Loader2 className="w-4 h-4 text-orange-400 animate-spin" />
                Retraining Models...
              </>
            ) : (
              <>
                <Rocket className="w-4 h-4 text-orange-400" />
                Retrain Models (Live DB)
              </>
            )}
          </button>

          {/* Dynamic Status Message Pop-up */}
          {retrainStatus && (
            <div className={`p-3 rounded-md text-xs border leading-relaxed ${retrainStatus.type === 'success' ? 'bg-emerald-950/30 border-emerald-900/50 text-emerald-400' : 'bg-red-950/30 border-red-900/50 text-red-400'}`}>
              {retrainStatus.message}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Reusable micro-component for the green status boxes
function StatusBadge({ icon: Icon, text }: { icon: React.ElementType, text: string }) {
  return (
    <div className="flex items-center gap-3 bg-emerald-950/20 border border-emerald-900/50 rounded-md p-3 shadow-sm">
      <Icon className="w-4 h-4 text-emerald-500 shrink-0" />
      <span className="text-[13px] font-medium text-emerald-500 leading-snug">{text}</span>
    </div>
  );
}