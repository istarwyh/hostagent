export interface StandaloneConfig {
  deploymentUrl: string;
  assistantId: string;
  langsmithApiKey?: string;
}

const CONFIG_STORAGE_KEY = "deep-agents-ui-config";

export function getConfig(): StandaloneConfig | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(CONFIG_STORAGE_KEY);
    if (!stored) return null;
    const config: unknown = JSON.parse(stored);
    if (!config || typeof config !== "object") return null;
    const value = config as Partial<StandaloneConfig>;
    if (
      typeof value.deploymentUrl !== "string" ||
      !value.deploymentUrl ||
      typeof value.assistantId !== "string" ||
      !value.assistantId ||
      (value.langsmithApiKey !== undefined &&
        typeof value.langsmithApiKey !== "string")
    ) {
      return null;
    }
    return value as StandaloneConfig;
  } catch {
    return null;
  }
}

export function saveConfig(config: StandaloneConfig): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(config));
}
