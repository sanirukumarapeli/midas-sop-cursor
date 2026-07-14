"use client";

import React from "react";
import dynamic from "next/dynamic";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ChartDataPayload, KpiMetric } from "@/lib/chartTypes";
import { formatReadableProse } from "@/lib/formatProse";

const SopChart = dynamic(() => import("./SopChart"), { ssr: false });

export interface AnalyticalDashboardProps {
  executiveSummary?: string;
  kpiMetrics?: KpiMetric[] | null;
  charts?: ChartDataPayload[];
  markdownTable?: string | null;
  strategicInsights?: string | null;
  recommendations?: string | null;
  isError?: boolean;
  tokenFooter?: React.ReactNode;
}

function isValidContent(val: unknown): boolean {
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
}

const proseListClassName = [
  "text-zinc-300 text-sm leading-relaxed",
  "[&_p]:mb-4 [&_p:last-child]:mb-0",
  "[&_ol]:my-4 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:space-y-3",
  "[&_ul]:my-4 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-3",
  "[&_li]:pl-1 [&_li]:leading-relaxed [&_li]:marker:text-zinc-500",
  "[&_li>p]:mb-1",
  "[&_strong]:text-zinc-100 [&_strong]:font-semibold",
  "[&_h1]:text-base [&_h2]:text-base [&_h3]:text-base",
  "[&_h1]:font-semibold [&_h2]:font-semibold [&_h3]:font-semibold",
  "[&_h1]:text-zinc-100 [&_h2]:text-zinc-100 [&_h3]:text-zinc-100",
  "[&_h1]:mt-5 [&_h2]:mt-5 [&_h3]:mt-5 [&_h1]:mb-2 [&_h2]:mb-2 [&_h3]:mb-2",
].join(" ");

function ReadableProse({ content }: { content: string }) {
  return (
    <div className={proseListClassName}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {formatReadableProse(content)}
      </ReactMarkdown>
    </div>
  );
}

function KpiStrip({ metrics }: { metrics: KpiMetric[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {metrics.slice(0, 4).map((kpi, idx) => {
        const emphasis = kpi.emphasis || "neutral";
        const valueClass =
          emphasis === "positive"
            ? "text-emerald-400"
            : emphasis === "negative"
              ? "text-orange-400"
              : "text-zinc-100";

        return (
          <div
            key={`${kpi.label}-${idx}`}
            className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 px-4 py-3"
          >
            <div className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
              {kpi.label}
            </div>
            <div className={`text-xl font-semibold tabular-nums ${valueClass}`}>
              {kpi.value}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function AnalyticalDashboard({
  executiveSummary,
  kpiMetrics,
  charts = [],
  markdownTable,
  strategicInsights,
  recommendations,
  isError = false,
  tokenFooter,
}: AnalyticalDashboardProps) {
  const validCharts = charts.filter(
    (c) =>
      c &&
      c.x_axis?.length &&
      c.datasets?.length &&
      isValidContent(c)
  );

  const compositionCharts = validCharts.filter((c) =>
    ["pie", "stacked_bar"].includes(c.chart_type)
  );
  const primaryCharts = validCharts.filter(
    (c) => !["pie", "stacked_bar"].includes(c.chart_type)
  );

  const showCompositionGrid = compositionCharts.length === 2;

  return (
    <div className="space-y-6">
      <div>
        {!isError && (
          <h3 className="text-lg font-medium mb-2 text-zinc-400">Executive Summary</h3>
        )}
        {isError && (
          <h3 className="text-lg font-medium mb-2 text-red-400">System Error</h3>
        )}
        <div className="font-serif text-zinc-200 leading-relaxed whitespace-pre-wrap text-[17px] prose prose-invert max-w-none">
          <ReactMarkdown>{executiveSummary || ""}</ReactMarkdown>
        </div>
      </div>

      {kpiMetrics && kpiMetrics.length > 0 && <KpiStrip metrics={kpiMetrics} />}

      {primaryCharts.map((chart, idx) => (
        <SopChart key={`primary-${chart.title}-${idx}`} chartData={chart} />
      ))}

      {showCompositionGrid ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {compositionCharts.map((chart, idx) => (
            <SopChart key={`comp-${chart.title}-${idx}`} chartData={chart} />
          ))}
        </div>
      ) : (
        compositionCharts.map((chart, idx) => (
          <SopChart key={`comp-${chart.title}-${idx}`} chartData={chart} />
        ))
      )}

      {isValidContent(markdownTable) && markdownTable && (
        <div className="overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-900/30">
          <div
            className="
              w-full text-sm text-left
              [&_table]:w-full [&_table]:table-fixed [&_table]:border-collapse [&_table]:text-left
              [&_thead]:bg-zinc-900/60 [&_thead]:border-b [&_thead]:border-zinc-700/80
              [&_th]:px-3 [&_th]:sm:px-5 [&_th]:py-3 [&_th]:sm:py-4 [&_th]:font-medium [&_th]:text-zinc-300 [&_th]:tracking-wide
              [&_th]:whitespace-normal [&_th]:break-words [&_th]:align-top
              [&_td]:px-3 [&_td]:sm:px-5 [&_td]:py-2.5 [&_td]:sm:py-3 [&_td]:text-zinc-400
              [&_td]:border-b [&_td]:border-zinc-800/50 [&_td]:whitespace-normal [&_td]:break-words [&_td]:align-top
              [&_tr:hover]:bg-zinc-800/30 [&_tbody_tr:last-child_td]:border-0 transition-colors
            "
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdownTable}</ReactMarkdown>
          </div>
        </div>
      )}

      {(isValidContent(strategicInsights) || isValidContent(recommendations)) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
          {isValidContent(strategicInsights) && (
            <Card className={`bg-zinc-900/30 border-zinc-800/80 ${isError ? "border-red-900/40" : ""}`}>
              <CardHeader>
                <CardTitle className="text-amber-400/90 text-base font-medium">
                  {isError ? "Error Diagnostics" : "Strategic Insights"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ReadableProse content={strategicInsights || ""} />
              </CardContent>
            </Card>
          )}

          {isValidContent(recommendations) && (
            <Card className={`bg-zinc-900/30 border-zinc-800/80 ${isError ? "border-red-900/40" : ""}`}>
              <CardHeader>
                <CardTitle className="text-emerald-400/90 text-base font-medium">
                  {isError ? "Required Actions" : "Recommendations"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ReadableProse content={recommendations || ""} />
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {tokenFooter}
    </div>
  );
}
