"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import { Sparkles } from "lucide-react";
import AnalyticalDashboard from "./AnalyticalDashboard";
import type { ChartDataPayload, KpiMetric } from "@/lib/chartTypes";

interface AssistantPayload {
  response_type?: "answer" | "clarification" | string;
  clarification_options?: string[] | null;
  clarification_field?: string | null;
  executive_summary?: string;
  kpi_metrics?: KpiMetric[] | null;
  visual_charts?: ChartDataPayload[] | null;
  visual_chart?: ChartDataPayload | null;
  markdown_table?: string;
  strategic_insights?: string;
  recommendations?: string;
  message?: string;
  answer?: string;
  response?: string;
  text?: string;
  output?: string;
  usage?: {
    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
  };
  [key: string]: unknown;
}

interface ChatMessage {
  role: "user" | "assistant" | string;
  content: string | AssistantPayload;
}

function flattenAssistantForHistory(payload: AssistantPayload): string {
  const summary = payload.executive_summary || "";
  if (
    payload.response_type === "clarification" &&
    Array.isArray(payload.clarification_options) &&
    payload.clarification_options.length > 0
  ) {
    const field = payload.clarification_field
      ? ` Field: ${payload.clarification_field}.`
      : "";
    const opts = payload.clarification_options.map((o, i) => `${i + 1}. ${o}`).join("\n");
    return `${summary}\n\nClarification options offered:${field}\n${opts}`;
  }
  return summary || JSON.stringify(payload);
}

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export default function ChatDashboard() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [greeting, setGreeting] = useState("Welcome");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef<ChatMessage[]>([]);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    setGreeting(getGreeting());
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    const handleClearChat = () => {
      setMessages([]);
    };

    window.addEventListener("clearChatHistory", handleClearChat);
    return () => window.removeEventListener("clearChatHistory", handleClearChat);
  }, []);

  const sendText = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    const historySnapshot = messagesRef.current;
    const newMessages: ChatMessage[] = [...historySnapshot, { role: "user", content: trimmed }];
    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    try {
      const formattedHistory = historySnapshot.map((m) => {
        let textContent = "";
        if (typeof m.content === "string") {
          textContent = m.content;
        } else if (typeof m.content === "object" && m.content !== null) {
          textContent = flattenAssistantForHistory(m.content as AssistantPayload);
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
          input: trimmed,
          chat_history: formattedHistory,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API Error ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data }]);
    } catch (error: unknown) {
      console.error("Failed to fetch:", error);

      const errorMessage =
        error instanceof Error ? error.message : "Connection refused or socket hang up.";

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: {
            executive_summary: "⚠️ Backend System Failure",
            strategic_insights: `The UI successfully sent the request, but the Python backend crashed. \n\n**Error Details:** ${errorMessage}`,
            recommendations:
              "1. Open your Python terminal where FastAPI is running.\n2. Look at the bottom for the red Traceback error.\n3. Fix the Python error and restart the backend server.",
            visual_chart: null,
            markdown_table: undefined,
          } as AssistantPayload,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading]);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    await sendText(input);
  };

  const isEmpty = messages.length === 0 && !isLoading;

  return (
    <div className="flex flex-col h-screen w-full bg-[#1a1a1a] text-zinc-200 overflow-hidden">
      <div className="flex-1 overflow-y-auto w-full scroll-smooth">
        {isEmpty ? (
          <div className="flex h-full min-h-[50vh] items-center justify-center px-6 pb-8">
            <div className="flex items-center gap-3">
              <Sparkles className="h-7 w-7 shrink-0 text-orange-400/90" strokeWidth={1.5} />
              <h1 className="font-serif text-3xl sm:text-4xl text-zinc-100 tracking-tight">
                {greeting}
              </h1>
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto px-6 pt-10 pb-8 space-y-10">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={
                    msg.role === "user"
                      ? "max-w-[75%] rounded-2xl bg-zinc-800/80 px-5 py-3.5 text-zinc-100"
                      : "w-full max-w-full"
                  }
                >
                  {msg.role === "user" && (
                    <p className="text-[15px] leading-relaxed">{msg.content as string}</p>
                  )}

                  {msg.role === "assistant" && typeof msg.content === "string" && (
                    <p className="font-serif text-[17px] text-zinc-200 leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                    </p>
                  )}

                  {msg.role === "assistant" &&
                    typeof msg.content === "object" &&
                    msg.content !== null &&
                    (() => {
                      const c = msg.content as AssistantPayload;

                      const isValidData = (val: unknown) => {
                        if (val === null || val === undefined) return false;
                        if (typeof val === "string") {
                          const clean = val.trim().toLowerCase();
                          if (!clean) return false;
                          if (["none", "n/a", "null", "empty", "no data", "na"].includes(clean))
                            return false;
                          if (
                            clean.includes("failed to parse") ||
                            clean.includes("failed to generate")
                          )
                            return false;
                          return true;
                        }
                        if (typeof val === "object") {
                          if (Array.isArray(val)) return val.length > 0;
                          return Object.keys(val as object).length > 0;
                        }
                        return true;
                      };

                      const charts: ChartDataPayload[] = [];
                      if (Array.isArray(c.visual_charts)) {
                        charts.push(...c.visual_charts.filter((ch) => isValidData(ch)));
                      }
                      if (charts.length === 0 && isValidData(c.visual_chart) && c.visual_chart) {
                        charts.push(c.visual_chart);
                      }

                      const hasCharts = charts.length > 0;
                      const hasKpis = isValidData(c.kpi_metrics);
                      const hasTable = isValidData(c.markdown_table);
                      const hasInsights = isValidData(c.strategic_insights);
                      const hasRecs = isValidData(c.recommendations);
                      const isError =
                        typeof c.executive_summary === "string" &&
                        c.executive_summary.includes("⚠️");

                      const clarificationOptions = Array.isArray(c.clarification_options)
                        ? c.clarification_options.filter(
                            (o) => typeof o === "string" && o.trim().length > 0
                          )
                        : [];
                      const isClarification =
                        c.response_type === "clarification" && clarificationOptions.length > 0;

                      const TokenTracker =
                        c.usage && (c.usage.input_tokens || c.usage.output_tokens) ? (
                          <div className="flex justify-end items-center gap-4 mt-6 pt-4 border-t border-zinc-800/50 text-xs text-zinc-600 font-mono">
                            <div className="flex items-center gap-1.5">
                              <span className="text-zinc-600">In:</span>
                              <span className="font-medium text-zinc-500">
                                {c.usage.input_tokens?.toLocaleString() || 0}
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <span className="text-zinc-600">Out:</span>
                              <span className="font-medium text-zinc-500">
                                {c.usage.output_tokens?.toLocaleString() || 0}
                              </span>
                            </div>
                            {c.usage.total_tokens && (
                              <div className="flex items-center gap-1 border-l border-zinc-700/60 pl-4 ml-1">
                                <span className="text-zinc-600">Total:</span>
                                <span className="font-medium text-zinc-400">
                                  {c.usage.total_tokens.toLocaleString()}
                                </span>
                              </div>
                            )}
                          </div>
                        ) : null;

                      if (isClarification) {
                        return (
                          <div className="flex flex-col gap-4">
                            <div className="prose prose-invert max-w-none font-serif text-[17px] text-zinc-200 leading-relaxed">
                              <ReactMarkdown>
                                {c.executive_summary ||
                                  "Which of these did you mean? Please select one:"}
                              </ReactMarkdown>
                            </div>
                            <p className="text-sm text-zinc-500">
                              Click one option below to continue
                            </p>
                            <div
                              className="flex flex-col gap-2.5"
                              role="group"
                              aria-label="Clarification options"
                            >
                              {clarificationOptions.map((option, optionIndex) => (
                                <button
                                  key={option}
                                  type="button"
                                  disabled={isLoading}
                                  onClick={() => sendText(option)}
                                  className="group w-full flex items-center gap-3 text-left px-4 py-3 rounded-xl border border-zinc-700/80 bg-zinc-900/40 text-zinc-100 cursor-pointer transition-colors hover:bg-zinc-800/80 hover:border-zinc-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1a1a1a] disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-zinc-600 text-xs font-medium text-zinc-400 group-hover:border-zinc-400 group-hover:text-zinc-200">
                                    {optionIndex + 1}
                                  </span>
                                  <span className="flex-1 text-[15px] leading-snug">{option}</span>
                                  <span className="shrink-0 text-zinc-500 text-sm group-hover:text-zinc-300">
                                    Select →
                                  </span>
                                </button>
                              ))}
                            </div>
                            {TokenTracker}
                          </div>
                        );
                      }

                      const isAnalytical =
                        hasCharts || hasKpis || hasTable || hasInsights || hasRecs || isError;

                      if (!isAnalytical) {
                        const fallbackText =
                          "I processed that, but the data returned an unexpected format. Could you rephrase your question?";

                        return (
                          <div className="flex flex-col">
                            <div className="prose prose-invert max-w-none font-serif text-[17px] text-zinc-200 leading-relaxed">
                              <ReactMarkdown>
                                {c.executive_summary || fallbackText}
                              </ReactMarkdown>
                            </div>
                            {TokenTracker}
                          </div>
                        );
                      }

                      return (
                        <AnalyticalDashboard
                          executiveSummary={c.executive_summary}
                          kpiMetrics={hasKpis ? (c.kpi_metrics as KpiMetric[]) : null}
                          charts={charts}
                          markdownTable={c.markdown_table}
                          strategicInsights={c.strategic_insights}
                          recommendations={c.recommendations}
                          isError={isError}
                          tokenFooter={TokenTracker}
                        />
                      );
                    })()}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="text-zinc-500 animate-pulse flex items-center gap-2 pt-2">
                <div className="h-1.5 w-1.5 bg-zinc-500 rounded-full" />
                <div className="h-1.5 w-1.5 bg-zinc-500 rounded-full" />
                <div className="h-1.5 w-1.5 bg-zinc-500 rounded-full" />
                <span className="text-sm">Analyzing S&OP scenarios...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <div className="w-full shrink-0 px-4 pb-3 pt-1 strategy-input-box">
        <form onSubmit={sendMessage} className="max-w-3xl mx-auto">
          <div className="flex items-end gap-2 rounded-3xl border border-zinc-700/70 bg-[#2b2b2b] px-3 py-2.5 shadow-sm focus-within:border-zinc-600">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="How can I help you today?"
              className="flex-1 bg-transparent px-3 py-3 text-[15px] text-zinc-100 placeholder-zinc-500 focus:outline-none font-serif"
            />
            <button
              type="submit"
              disabled={isLoading}
              className="shrink-0 rounded-2xl bg-zinc-100 hover:bg-white text-zinc-900 px-5 py-2.5 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? "Processing" : "Analyze"}
            </button>
          </div>
        </form>
        <p className="mt-3 text-center text-xs text-zinc-500">
          Midason is AI and can make mistakes. Please double-check responses.
        </p>
      </div>
    </div>
  );
}
