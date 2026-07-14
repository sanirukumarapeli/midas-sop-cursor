"use client";

import React, { useState, useRef, useEffect } from "react";
import dynamic from "next/dynamic";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Safely import the chart component only on the client side to bypass Next SSR issues
const SopChart = dynamic(() => import("./SopChart"), { ssr: false });

// 🚨 NEW: Define the exact shape of the data the Python backend sends
interface AssistantPayload {
  executive_summary?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  visual_chart?: any;
  markdown_table?: string;
  strategic_insights?: string;
  recommendations?: string;
  message?: string;
  answer?: string;
  response?: string;
  text?: string;
  output?: string;
  // 🚨 NEW: Token usage tracking interface
  usage?: {
    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
  };
  [key: string]: unknown; // Catch-all for any other conversational keys
}

// 🚨 NEW: Define the chat message structure
interface ChatMessage {
  role: "user" | "assistant" | string;
  content: string | AssistantPayload;
}

export default function ChatDashboard() {
  // 🚨 FIXED: Replaced <any[]> with <ChatMessage[]>
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Listen for the reset signal from the Sidebar
  useEffect(() => {
    const handleClearChat = () => {
      setMessages([]); // Instantly clears the UI and the frontend memory
    };

    window.addEventListener('clearChatHistory', handleClearChat);
    return () => window.removeEventListener('clearChatHistory', handleClearChat);
  }, []);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const newMessages: ChatMessage[] = [...messages, { role: "user", content: input }];
    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    try {
      // Flatten complex objects into clean plain text structures for history
      const formattedHistory = messages.map((m) => {
        let textContent = "";
        if (typeof m.content === "string") {
          textContent = m.content;
        } else if (typeof m.content === "object" && m.content !== null) {
          const payload = m.content as AssistantPayload;
          textContent = payload.executive_summary || JSON.stringify(payload);
        }
        return {
          role: m.role,
          content: textContent,
        };
      });

      const response = await fetch("http://127.0.0.1:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input: input,
          chat_history: formattedHistory,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API Error ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data }]);
      
    } catch (error: unknown) { // 🚨 FIXED: Replaced "error: any" with "error: unknown"
      console.error("Failed to fetch:", error);
      
      // 🚨 FIXED: Safely extract the error message from the unknown type
      const errorMessage = error instanceof Error ? error.message : "Connection refused or socket hang up.";

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: {
            executive_summary: "⚠️ Backend System Failure",
            strategic_insights: `The UI successfully sent the request, but the Python backend crashed. \n\n**Error Details:** ${errorMessage}`,
            recommendations: "1. Open your Python terminal where FastAPI is running.\n2. Look at the bottom for the red Traceback error.\n3. Fix the Python error and restart the backend server.",
            visual_chart: null,
            markdown_table: undefined
          } as AssistantPayload,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen w-full bg-slate-950 text-slate-200 overflow-hidden">
      
      {/* Native CSS Scroll Container */}
      <div className="flex-1 overflow-y-auto w-full p-6 bg-slate-950 scroll-smooth">
        <div className="max-w-5xl mx-auto space-y-8 pb-12">
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[90%] w-full rounded-xl p-6 ${msg.role === "user" ? "bg-blue-600 text-white ml-auto max-w-[70%]" : "bg-slate-900 border border-slate-800"}`}>
                
                {/* User Message Rendering */}
                {msg.role === "user" && <p className="text-lg">{msg.content as string}</p>}

                {/* Assistant Plain Text Fallback Rendering */}
                {msg.role === "assistant" && typeof msg.content === "string" && (
                  <p className="text-slate-200 leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                )}

                {/* Assistant Structured Object Rendering */}
                {msg.role === "assistant" && typeof msg.content === "object" && msg.content !== null && (() => {
                  const c = msg.content as AssistantPayload;

                  // 🚨 FIXED: Replaced "val: any" with "val: unknown"
                  const isValidData = (val: unknown) => {
                    if (val === null || val === undefined) return false;
                    if (typeof val === "string") {
                      const clean = val.trim().toLowerCase();
                      if (!clean) return false;
                      if (["none", "n/a", "null", "empty", "no data", "na"].includes(clean)) return false;
                      if (clean.includes("failed to parse") || clean.includes("failed to generate")) return false;
                      return true;
                    }
                    if (typeof val === "object") {
                      if (Array.isArray(val)) return val.length > 0;
                      return Object.keys(val as object).length > 0;
                    }
                    return true;
                  };

                  const hasChart = isValidData(c.visual_chart);
                  const hasTable = isValidData(c.markdown_table);
                  const hasInsights = isValidData(c.strategic_insights);
                  const hasRecs = isValidData(c.recommendations);
                  const isError = typeof c.executive_summary === 'string' && c.executive_summary.includes('⚠️');

                  const isAnalytical = hasChart || hasTable || hasInsights || hasRecs || isError;

                  // 🚨 NEW: Reusable Token Tracker Footer UI
                  const TokenTracker = c.usage && (c.usage.input_tokens || c.usage.output_tokens) ? (
                    <div className="flex justify-end items-center gap-4 mt-6 pt-4 border-t border-slate-800/60 text-xs text-slate-500 font-mono">
                      <div className="flex items-center gap-1.5">
                        <span className="text-slate-600">In:</span> 
                        <span className="font-semibold text-slate-400">{c.usage.input_tokens?.toLocaleString() || 0}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-slate-600">Out:</span> 
                        <span className="font-semibold text-slate-400">{c.usage.output_tokens?.toLocaleString() || 0}</span>
                      </div>
                      {c.usage.total_tokens && (
                        <div className="flex items-center gap-1 border-l border-slate-700 pl-4 ml-1">
                          <span className="text-slate-600">Total:</span>
                          <span className="font-semibold text-blue-400/80">{c.usage.total_tokens.toLocaleString()}</span>
                        </div>
                      )}
                    </div>
                  ) : null;

                  // 1. CONVERSATIONAL MODE
                  if (!isAnalytical) {
                    // We expect the AI to always use executive_summary, even for casual chat.
                    const fallbackText = "I processed that, but the data returned an unexpected format. Could you rephrase your question?";
                    
                    return (
                      <div className="flex flex-col h-full">
                        <div className="prose prose-invert max-w-none text-slate-200 text-lg leading-relaxed">
                          <ReactMarkdown>{c.executive_summary || fallbackText}</ReactMarkdown>
                        </div>
                        {TokenTracker}
                      </div>
                    );
                  }

                  // 2. ANALYTICAL DASHBOARD MODE
                  return (
                    <div className="space-y-6">
                      {/* Executive Summary Block */}
                      <div>
                        <h3 className={`text-xl font-bold mb-2 ${isError ? 'text-red-500' : 'text-blue-400'}`}>
                          {isError ? 'System Error' : 'Executive Summary'}
                        </h3>
                        <div className="text-slate-300 leading-relaxed whitespace-pre-wrap text-base prose prose-invert max-w-none">
                           <ReactMarkdown>{c.executive_summary || ""}</ReactMarkdown>
                        </div>
                      </div>

                      {/* Dynamic Chart Integration */}
                      {hasChart && c.visual_chart && (
                        <SopChart chartData={c.visual_chart} />
                      )}

                      {/* Dynamic Markdown Table Integration */}
                      {hasTable && c.markdown_table && (
                        <div className="mt-6 overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/40 shadow-sm custom-scrollbar">
                          <div className="
                            w-full text-sm text-left
                            [&_table]:w-full [&_table]:border-collapse [&_table]:text-left
                            [&_thead]:bg-slate-900/80 [&_thead]:border-b [&_thead]:border-slate-700
                            [&_th]:px-5 [&_th]:py-4 [&_th]:font-semibold [&_th]:text-blue-400 [&_th]:whitespace-nowrap [&_th]:tracking-wide
                            [&_td]:px-5 [&_td]:py-3 [&_td]:text-slate-300 [&_td]:border-b [&_td]:border-slate-800/50 [&_td]:whitespace-nowrap
                            [&_tr:hover]:bg-slate-800/30 [&_tbody_tr:last-child_td]:border-0 transition-colors
                          ">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {c.markdown_table}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}

                      {/* Insights & Recommendations Grid */}
                      {(hasInsights || hasRecs) && (
                        // 🚨 THE FIX: Added 'items-start' so the cards don't stretch to equal heights
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6 items-start">
                          {hasInsights && (
                            <Card className={`bg-slate-950 border-slate-800 ${isError ? 'border-red-900/50' : ''}`}>
                              <CardHeader>
                                <CardTitle className="text-amber-400 text-lg">
                                  {isError ? 'Error Diagnostics' : 'Strategic Insights'}
                                </CardTitle>
                              </CardHeader>
                              <CardContent>
                                {/* 🚨 THE FIX: Using native arbitrary selectors to force margins on paragraphs and lists */}
                                <div className="text-slate-400 text-sm leading-relaxed [&_p]:mb-4 [&_p:last-child]:mb-0 [&_ul]:mb-4 [&_ul]:pl-5 [&_ul]:list-disc [&_li]:mb-3">
                                  <ReactMarkdown>{c.strategic_insights || ""}</ReactMarkdown>
                                </div>
                              </CardContent>
                            </Card>
                          )}
                          
                          {hasRecs && (
                            <Card className={`bg-slate-950 border-slate-800 ${isError ? 'border-red-900/50' : ''}`}>
                              <CardHeader>
                                <CardTitle className="text-emerald-400 text-lg">
                                  {isError ? 'Required Actions' : 'Recommendations'}
                                </CardTitle>
                              </CardHeader>
                              <CardContent>
                                {/* 🚨 THE FIX: Using native arbitrary selectors to force margins on paragraphs and lists */}
                                <div className="text-slate-400 text-sm leading-relaxed [&_p]:mb-4 [&_p:last-child]:mb-0 [&_ul]:mb-4 [&_ul]:pl-5 [&_ul]:list-disc [&_li]:mb-3">
                                  <ReactMarkdown>{c.recommendations || ""}</ReactMarkdown>
                                </div>
                              </CardContent>
                            </Card>
                          )}
                        </div>
                      )}
                      
                      {TokenTracker}
                    </div>
                  );
                })()}
              </div>
            </div>
          ))}
          {isLoading && (
             <div className="text-slate-500 animate-pulse flex items-center gap-2 pt-4">
                <div className="h-2 w-2 bg-blue-500 rounded-full"></div>
                <div className="h-2 w-2 bg-blue-500 rounded-full"></div>
                <div className="h-2 w-2 bg-blue-500 rounded-full"></div>
                <span>Analyzing S&OP scenarios...</span>
             </div>
          )}

          {/* Auto-scroll anchor */}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Bar */}
      <div className="w-full p-6 bg-slate-950 border-t border-slate-800/80 strategy-input-box">
        <form onSubmit={sendMessage} className="max-w-5xl mx-auto flex gap-4">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask the S&OP Copilot..."
            className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-6 py-4 focus:outline-none focus:ring-2 focus:ring-blue-500 text-lg text-slate-100 placeholder-slate-500"
          />
          <button type="submit" disabled={isLoading} className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 rounded-lg font-semibold transition-colors disabled:opacity-50">
            {isLoading ? "Processing" : "Analyze"}
          </button>
        </form>
      </div>
    </div>
  );
}