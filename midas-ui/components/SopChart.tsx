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
  ReferenceLine,
  LabelList,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartDataPayload,
  ChartDataset,
  CHART_COLORS,
  POSITIVE_COLOR,
  NEGATIVE_COLOR,
  REFERENCE_LINE_COLOR,
} from "@/lib/chartTypes";

interface DataPoint {
  name: string;
  [key: string]: string | number;
}

const formatYAxis = (value: number, unit?: string) => {
  if (value === null || value === undefined || isNaN(value)) return "";

  if (unit === "PERCENT") {
    return `${value.toFixed(1)}%`;
  }

  if (unit === "USD") {
    if (value >= 1e6 || value <= -1e6) return `$${(value / 1e6).toFixed(1)}M`;
    if (value >= 1e3 || value <= -1e3) return `$${(value / 1e3).toFixed(0)}K`;
    return `$${value.toLocaleString()}`;
  }

  if (unit === "DPs") {
    if (value >= 1e6 || value <= -1e6) return `${(value / 1e6).toFixed(1)}M DPs`;
    if (value >= 1e3 || value <= -1e3) return `${(value / 1e3).toFixed(0)}K DPs`;
    return `${value.toLocaleString()} DPs`;
  }

  if (value >= 1e6 || value <= -1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3 || value <= -1e3) return `${(value / 1e3).toFixed(0)}K`;
  return value.toLocaleString();
};

const formatRechartsData = (chartData: ChartDataPayload): DataPoint[] => {
  if (!chartData || !chartData.x_axis || !chartData.datasets) return [];
  return chartData.x_axis.map((label: string, index: number) => {
    const dataPoint: DataPoint = { name: label };
    chartData.datasets.forEach((dataset: ChartDataset) => {
      dataPoint[dataset.name] = dataset.data[index] ?? 0;
    });
    return dataPoint;
  });
};

const resolveUnit = (chartData: ChartDataPayload): string => {
  let unit = chartData.y_axis_unit || "generic";
  const hasDPsInName = chartData.datasets.some((ds) => ds.name.includes("DP"));
  const hasUSDInName = chartData.datasets.some(
    (ds) => ds.name.includes("USD") || ds.name.includes("Revenue")
  );
  const hasPctInName = chartData.datasets.some(
    (ds) => ds.name.includes("%") || ds.name.toLowerCase().includes("mom") || ds.name.toLowerCase().includes("yoy")
  );

  if (unit === "PERCENT" || hasPctInName) return "PERCENT";
  if (hasDPsInName) return "DPs";
  if (hasUSDInName) return "USD";
  return unit;
};

const chartShell = (title: string, children: React.ReactNode, height = 360) => (
  <Card className="bg-zinc-900/40 border-zinc-800/80 text-white shadow-none">
    <CardHeader className="pb-2">
      <CardTitle className="text-xs font-medium tracking-widest uppercase text-zinc-500">
        {title}
      </CardTitle>
    </CardHeader>
    <CardContent style={{ height }}>
      {children}
    </CardContent>
  </Card>
);

const tooltipStyle = {
  backgroundColor: "#27272a",
  borderColor: "#3f3f46",
  borderRadius: "8px",
};

export default function SopChart({ chartData }: { chartData: ChartDataPayload | null }) {
  const data = useMemo(() => {
    if (!chartData) return [];
    return formatRechartsData(chartData);
  }, [chartData]);

  if (!chartData || !chartData.datasets?.length || !chartData.x_axis?.length) {
    return null;
  }

  const unit = resolveUnit(chartData);
  const colors = CHART_COLORS;

  // --- PIE / DONUT ---
  if (chartData.chart_type === "pie") {
    const pieData = chartData.x_axis.map((label, index) => ({
      name: label,
      value: chartData.datasets[0].data[index] || 0,
    }));

    return chartShell(
      chartData.title,
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(value: unknown) => [
              formatYAxis(Number(value), unit),
              chartData.datasets[0].name,
            ]}
          />
          <Legend wrapperStyle={{ paddingTop: "12px" }} />
          <Pie
            data={pieData}
            cx="50%"
            cy="48%"
            innerRadius={58}
            outerRadius={110}
            paddingAngle={4}
            dataKey="value"
            stroke="none"
          >
            {pieData.map((_, index) => (
              <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    );
  }

  // --- DIVERGING BAR (MoM %) ---
  if (chartData.chart_type === "diverging_bar") {
    const seriesName = chartData.datasets[0].name;
    return chartShell(
      chartData.title,
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: 10, right: 10, top: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
          <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 12 }} />
          <YAxis
            stroke="#94a3b8"
            tickFormatter={(value: unknown) => formatYAxis(Number(value), "PERCENT")}
            width={55}
          />
          <ReferenceLine y={0} stroke="#64748b" strokeWidth={1} />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(value: unknown, name: unknown) => [
              formatYAxis(Number(value), "PERCENT"),
              String(name),
            ]}
            cursor={{ fill: "rgba(255, 255, 255, 0.04)" }}
          />
          <Bar dataKey={seriesName} radius={[4, 4, 4, 4]}>
            {data.map((entry, index) => {
              const val = Number(entry[seriesName]);
              return (
                <Cell
                  key={`div-${index}`}
                  fill={val >= 0 ? POSITIVE_COLOR : NEGATIVE_COLOR}
                />
              );
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }

  // --- HORIZONTAL BAR ---
  if (chartData.chart_type === "horizontal_bar") {
    const seriesName = chartData.datasets[0].name;
    return chartShell(
      chartData.title,
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          layout="vertical"
          data={data}
          margin={{ left: 8, right: 48, top: 8, bottom: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
          <XAxis
            type="number"
            stroke="#94a3b8"
            tickFormatter={(value: unknown) => formatYAxis(Number(value), unit)}
          />
          <YAxis
            type="category"
            dataKey="name"
            stroke="#94a3b8"
            width={72}
            tick={{ fontSize: 12 }}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(value: unknown, name: unknown) => [
              formatYAxis(Number(value), unit),
              String(name),
            ]}
            cursor={{ fill: "rgba(255, 255, 255, 0.04)" }}
          />
          <Bar dataKey={seriesName} fill={POSITIVE_COLOR} radius={[0, 4, 4, 0]}>
            <LabelList
              dataKey={seriesName}
              position="right"
              formatter={(label) => formatYAxis(Number(label), unit)}
              style={{ fill: "#94a3b8", fontSize: 11 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>,
      Math.max(280, data.length * 36 + 40)
    );
  }

  // --- DUAL AXIS ---
  if (chartData.chart_type === "dual_axis" && chartData.datasets.length >= 2) {
    return chartShell(
      chartData.title,
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ left: 15, right: 15 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
          <XAxis dataKey="name" stroke="#94a3b8" />
          <YAxis
            yAxisId="left"
            stroke={colors[0]}
            tickFormatter={(val) => formatYAxis(Number(val), "generic")}
            width={75}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            stroke={colors[1]}
            tickFormatter={(val) => formatYAxis(Number(val), "generic")}
            width={75}
          />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ paddingTop: "12px" }} />
          <Bar
            yAxisId="left"
            dataKey={chartData.datasets[0].name}
            fill={colors[0]}
            radius={[4, 4, 0, 0]}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey={chartData.datasets[1].name}
            stroke={colors[1]}
            strokeWidth={3}
            dot={{ r: 3 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    );
  }

  // --- BAR / STACKED / WATERFALL ---
  const isBarGraph = ["bar", "stacked_bar", "waterfall"].includes(chartData.chart_type);

  if (isBarGraph) {
    return chartShell(
      chartData.title,
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: 15 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
          <XAxis dataKey="name" stroke="#94a3b8" />
          <YAxis
            stroke="#94a3b8"
            tickFormatter={(value: unknown) => formatYAxis(Number(value), unit)}
            width={75}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(value: unknown, name: unknown) => [
              formatYAxis(Number(value), unit),
              String(name),
            ]}
            cursor={{ fill: "rgba(255, 255, 255, 0.05)" }}
          />
          <Legend wrapperStyle={{ paddingTop: "12px" }} />
          {chartData.datasets.map((ds: ChartDataset, i: number) => (
            <Bar
              key={ds.name}
              dataKey={ds.name}
              fill={colors[i % colors.length]}
              stackId={chartData.chart_type === "stacked_bar" ? "a" : undefined}
              radius={chartData.chart_type === "stacked_bar" ? [0, 0, 0, 0] : [4, 4, 0, 0]}
            >
              {chartData.chart_type === "waterfall" &&
                data.map((entry, index) => {
                  const val = Number(entry[ds.name]);
                  let cellColor = colors[0];
                  if (val > 0 && index !== 0 && index !== data.length - 1) {
                    cellColor = POSITIVE_COLOR;
                  }
                  if (val < 0) cellColor = NEGATIVE_COLOR;
                  return <Cell key={`cell-${index}`} fill={cellColor} />;
                })}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  // --- LINE (default) ---
  const avgFromData =
    chartData.datasets[0]?.data?.length > 0
      ? chartData.datasets[0].data.reduce((a, b) => a + b, 0) /
        chartData.datasets[0].data.length
      : null;

  const referenceValue =
    chartData.reference_value ??
    (chartData.show_average_line ? avgFromData : null);

  return chartShell(
    chartData.title,
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ left: 15, right: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
        <XAxis dataKey="name" stroke="#94a3b8" />
        <YAxis
          stroke="#94a3b8"
          tickFormatter={(value: unknown) => formatYAxis(Number(value), unit)}
          width={75}
        />
        {referenceValue != null && !Number.isNaN(referenceValue) && (
          <ReferenceLine
            y={referenceValue}
            stroke={REFERENCE_LINE_COLOR}
            strokeDasharray="6 4"
            strokeWidth={1.5}
            label={{
              value: "Avg",
              position: "insideTopRight",
              fill: REFERENCE_LINE_COLOR,
              fontSize: 11,
            }}
          />
        )}
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value: unknown, name: unknown) => [
            formatYAxis(Number(value), unit),
            String(name),
          ]}
        />
        <Legend wrapperStyle={{ paddingTop: "12px" }} />
        {chartData.datasets.map((ds: ChartDataset, i: number) => (
          <Line
            key={ds.name}
            type="monotone"
            dataKey={ds.name}
            stroke={colors[i % colors.length]}
            strokeWidth={i === 0 ? 2.5 : 2}
            strokeDasharray={i === 0 ? undefined : i === 1 ? "6 4" : "2 4"}
            dot={{ r: 3, fill: colors[i % colors.length] }}
            activeDot={{ r: 5 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
