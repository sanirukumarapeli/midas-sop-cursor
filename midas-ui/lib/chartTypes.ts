export interface ChartDataset {
  name: string;
  data: number[];
}

export interface ChartDataPayload {
  title: string;
  chart_type: string;
  y_axis_unit?: string;
  x_axis: string[];
  datasets: ChartDataset[];
  show_average_line?: boolean;
  reference_value?: number | null;
}

export interface KpiMetric {
  label: string;
  value: string;
  emphasis?: "neutral" | "positive" | "negative";
}

export const CHART_COLORS = [
  "#3b82f6", // blue
  "#10b981", // emerald
  "#8b5cf6", // violet
  "#f59e0b", // amber
  "#f43f5e", // rose
  "#06b6d4", // cyan
];

export const POSITIVE_COLOR = "#10b981";
export const NEGATIVE_COLOR = "#f97316";
export const REFERENCE_LINE_COLOR = "#f59e0b";
