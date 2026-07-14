"use client";

import React, { useMemo } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// --- 🚨 STRICT TYPESCRIPT INTERFACES ---
interface ChartDataset {
  name: string;
  data: number[];
}

interface ChartDataPayload {
  title: string;
  chart_type: string; // "line" | "bar" | "pie" | "stacked_bar" | "waterfall" | "dual_axis"
  y_axis_unit?: string;
  x_axis: string[];
  datasets: ChartDataset[];
}

interface DataPoint {
  name: string;
  [key: string]: string | number;
}
// ----------------------------------------

// 1. DYNAMIC Y-AXIS FORMATTER
const formatYAxis = (value: number, unit?: string) => {
  if (value === null || value === undefined || isNaN(value)) return "";

  // Format for Revenue / Dollars
  if (unit === "USD") {
    if (value >= 1e6 || value <= -1e6) return `$${(value / 1e6).toFixed(1)}M`;
    if (value >= 1e3 || value <= -1e3) return `$${(value / 1e3).toFixed(0)}K`;
    return `$${value.toLocaleString()}`;
  }

  // Format for Volume / Quantities
  if (unit === "DPs") {
    if (value >= 1e6 || value <= -1e6) return `${(value / 1e6).toFixed(1)}M DPs`;
    if (value >= 1e3 || value <= -1e3) return `${(value / 1e3).toFixed(0)}K DPs`;
    return `${value.toLocaleString()} DPs`;
  }

  // Fallback generic formatting
  if (value >= 1e6 || value <= -1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3 || value <= -1e3) return `${(value / 1e3).toFixed(0)}K`;
  return value.toLocaleString();
};

const formatRechartsData = (chartData: ChartDataPayload): DataPoint[] => {
  if (!chartData || !chartData.x_axis || !chartData.datasets) return [];
  return chartData.x_axis.map((label: string, index: number) => {
    const dataPoint: DataPoint = { name: label };
    chartData.datasets.forEach((dataset: ChartDataset) => {
      dataPoint[dataset.name] = dataset.data[index];
    });
    return dataPoint;
  });
};

export default function SopChart({ chartData }: { chartData: ChartDataPayload | null }) {
  const data = useMemo(() => {
    if (!chartData) return [];
    return formatRechartsData(chartData);
  }, [chartData]);

  if (!chartData) return null;

  const colors = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444"];

  // --- 🚨 FRONTEND FAILSAFE AUTO DETECTION ---
  let unit = chartData.y_axis_unit || "generic";
  const hasDPsInName = chartData.datasets.some((ds) => ds.name.includes("DP"));
  const hasUSDInName = chartData.datasets.some((ds) => ds.name.includes("USD") || ds.name.includes("Revenue"));
  
  if (hasDPsInName) unit = "DPs";
  else if (hasUSDInName) unit = "USD";
  // ------------------------------------------

  // 1. PIE CHART RENDERING
  if (chartData.chart_type === "pie") {
    // Pie charts need a specific {name, value} array format
    const pieData = chartData.x_axis.map((label, index) => ({
      name: label,
      value: chartData.datasets[0].data[index] || 0
    }));

    return (
      <Card className="mt-6 mb-6 bg-slate-900 border-slate-800 text-white">
        <CardHeader><CardTitle>{chartData.title}</CardTitle></CardHeader>
        <CardContent style={{ height: '400px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Tooltip 
                contentStyle={{ backgroundColor: "#1e293b", borderColor: "#334155", borderRadius: '8px' }} 
                formatter={(value: unknown) => [formatYAxis(Number(value), unit), chartData.datasets[0].name]}
              />
              <Legend wrapperStyle={{ paddingTop: "20px" }} />
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={120}
                paddingAngle={5}
                dataKey="value"
                stroke="none"
              >
                {pieData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    );
  }

  // 2. DUAL-AXIS OVERLAY RENDERING
  if (chartData.chart_type === "dual_axis" && chartData.datasets.length >= 2) {
    return (
      <Card className="mt-6 mb-6 bg-slate-900 border-slate-800 text-white">
        <CardHeader><CardTitle>{chartData.title}</CardTitle></CardHeader>
        <CardContent style={{ height: '400px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ left: 15, right: 15 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis dataKey="name" stroke="#94a3b8" />
              <YAxis yAxisId="left" stroke={colors[0]} tickFormatter={(val) => formatYAxis(Number(val), "generic")} width={75} />
              <YAxis yAxisId="right" orientation="right" stroke={colors[1]} tickFormatter={(val) => formatYAxis(Number(val), "generic")} width={75} />
              <Tooltip contentStyle={{ backgroundColor: "#1e293b", borderColor: "#334155", borderRadius: '8px' }} />
              <Legend wrapperStyle={{ paddingTop: "20px" }} />
              {/* Force first dataset to Bar (Left Axis), second to Line (Right Axis) */}
              <Bar yAxisId="left" dataKey={chartData.datasets[0].name} fill={colors[0]} radius={[4, 4, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey={chartData.datasets[1].name} stroke={colors[1]} strokeWidth={3} dot={{ r: 4 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    );
  }

  // 3. BAR, STACKED BAR, & WATERFALL RENDERING
  const isBarGraph = ["bar", "stacked_bar", "waterfall"].includes(chartData.chart_type);
  
  return (
    <Card className="mt-6 mb-6 bg-slate-900 border-slate-800 text-white">
      <CardHeader>
        <CardTitle>{chartData.title}</CardTitle>
      </CardHeader>
      
      <CardContent style={{ height: '400px' }}>
        <ResponsiveContainer width="100%" height="100%">
          {isBarGraph ? (
            <BarChart data={data} margin={{ left: 15 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis dataKey="name" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" tickFormatter={(value: unknown) => formatYAxis(Number(value), unit)} width={75} />
              <Tooltip 
                contentStyle={{ backgroundColor: "#1e293b", borderColor: "#334155", borderRadius: '8px' }} 
                formatter={(value: unknown, name: unknown) => [formatYAxis(Number(value), unit), String(name)]}
                cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }}
              />
              <Legend wrapperStyle={{ paddingTop: "20px" }} />
              {chartData.datasets.map((ds: ChartDataset, i: number) => (
                <Bar 
                  key={ds.name} 
                  dataKey={ds.name} 
                  fill={colors[i % colors.length]} 
                  stackId={chartData.chart_type === "stacked_bar" ? "a" : undefined} 
                  radius={chartData.chart_type === "stacked_bar" ? [0, 0, 0, 0] : [4, 4, 0, 0]}
                >
                  {/* Waterfall visual styling (Green = positive, Red = negative) */}
                  {chartData.chart_type === "waterfall" && data.map((entry, index) => {
                    const val = Number(entry[ds.name]);
                    let cellColor = "#3b82f6"; // Default Blue
                    if (val > 0 && index !== 0 && index !== data.length - 1) cellColor = "#10b981"; // Green up
                    if (val < 0) cellColor = "#ef4444"; // Red down
                    return <Cell key={`cell-${index}`} fill={cellColor} />;
                  })}
                </Bar>
              ))}
            </BarChart>
          ) : (
            // 4. DEFAULT LINE CHART RENDERING
            <LineChart data={data} margin={{ left: 15 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis dataKey="name" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" tickFormatter={(value: unknown) => formatYAxis(Number(value), unit)} width={75} />
              <Tooltip 
                contentStyle={{ backgroundColor: "#1e293b", borderColor: "#334155", borderRadius: '8px' }} 
                formatter={(value: unknown, name: unknown) => [formatYAxis(Number(value), unit), String(name)]}
              />
              <Legend wrapperStyle={{ paddingTop: "20px" }} />
              {chartData.datasets.map((ds: ChartDataset, i: number) => (
                <Line 
                  key={ds.name} 
                  type="monotone" 
                  dataKey={ds.name} 
                  stroke={colors[i % colors.length]} 
                  strokeWidth={3}
                  dot={{ r: 4, fill: colors[i % colors.length] }}
                  activeDot={{ r: 6 }}
                />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}