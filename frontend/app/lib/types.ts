export interface Field {
  name: string;
  label: string;
  type: string;
  required: boolean;
  description?: string;
}

export interface SchemaResp { fields: Field[]; }

export interface Contact {
  id: string;
  name: string;
  phone: string;
  phone_valid: boolean;
  email?: string | null;
  department?: string | null;
  extra: Record<string, any>;
  status: string;
  attempts: number;
}

export interface ParsedImport {
  filename: string;
  columns: string[];
  mapping: Record<string, string>;
  contacts: Array<{
    name: string; phone: string; phone_valid: boolean;
    email?: string | null; department?: string | null; extra: Record<string, any>;
  }>;
  stats: { total: number; valid: number; invalid: number; duplicates: number };
  errors: string[];
}

export interface CampaignStats {
  total: number; pending: number; calling: number;
  completed: number; failed: number; no_answer: number; busy: number;
}

export interface Campaign {
  id: string;
  name: string;
  mode: string;
  instruction: string;
  extraction_schema: SchemaResp;
  organisation: string;
  voice: string;
  language: string;
  max_duration: number;
  concurrency: number;
  max_retries: number;
  status: string;
  created_at: string;
  stats?: CampaignStats;
  contact_count?: number;
}

export interface Call {
  id: string;
  campaign_id: string;
  contact_id: string;
  phone: string;
  status: string;
  state: string;
  duration: number;
  started_at?: string | null;
  ended_at?: string | null;
  recording_url?: string | null;
  extracted_data: Record<string, any>;
  error?: string | null;
  transcript?: Array<{ role: string; text: string; ts?: string }>;
  contact_name?: string;
}

export interface ResultsResp {
  campaign: string;
  columns: Array<{ name: string; label: string }>;
  rows: Array<Record<string, any>>;
}

export interface Overview {
  app: string;
  tagline: string;
  adapter: string;
  metrics: {
    total_calls: number; completed: number; successful: number; failed: number;
    avg_duration: number; information_collected: number;
    campaigns: number; contacts: number;
  };
}
