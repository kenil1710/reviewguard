/** The shapes ReviewGuard actually returns. Mirrors the contract's views; a
 *  field that can be UNAVAILABLE on chain is `number | null` here, never 0. */

export type TrustLevel =
  | "AUTHENTIC"
  | "SUSPICIOUS"
  | "MANIPULATED"
  | "INCONCLUSIVE";

export type Platform = "AMAZON" | "GOOGLE_PLAY" | "APP_STORE";

export type DimensionKey =
  | "timing_pattern"
  | "rating_distribution"
  | "review_quality"
  | "reviewer_credibility"
  | "engagement_signals";

export const DIMENSIONS: DimensionKey[] = [
  "timing_pattern",
  "rating_distribution",
  "review_quality",
  "reviewer_credibility",
  "engagement_signals",
];

export const DIMENSION_LABELS: Record<DimensionKey, string> = {
  timing_pattern: "Timing pattern",
  rating_distribution: "Rating distribution",
  review_quality: "Review quality",
  reviewer_credibility: "Reviewer credibility",
  engagement_signals: "Engagement signals",
};

export const DIMENSION_BLURBS: Record<DimensionKey, string> = {
  timing_pattern:
    "Are the reviews clustered on particular dates, or spread out over time? Natural products accumulate reviews steadily; bought batches arrive together.",
  rating_distribution:
    "Is the star histogram a shape a real product produces? Genuine listings keep a negative tail and a populated middle.",
  review_quality:
    "Are the reviews written or generated? Length, vocabulary variety and duplicate openings separate the two.",
  reviewer_credibility:
    "Do the reviewers look like people with a history? Verified-purchase share where the platform publishes it, identity shape where it does not.",
  engagement_signals:
    "Did anyone react? Helpful votes, customer photos and seller responses are hard to fake at scale.",
};

export interface Evidence {
  reviews_parsed: number;
  avg_rating_x10: number | null;
  total_ratings: number | null;
  rating_histogram: Record<"1" | "2" | "3" | "4" | "5", number | null>;
  dated_reviews: number;
  distinct_days: number;
  max_same_day: number;
  span_days: number;
  median_chars: number;
  short_pct: number;
  dup_open_pct: number;
  lexical_pct: number;
  verified_pct: number | null;
  distinct_names_pct: number;
  weak_handle_pct: number;
  helpful_pct: number | null;
  helpful_total: number | null;
  has_photos: boolean;
  has_response: boolean;
  page_chars: number;
  reviews_section: boolean;
}

export interface CheckRecord {
  found: true;
  check_id: number;
  seq: number;
  url_key: string;
  platform: Platform;
  title: string;
  source_url: string;
  overall: number;
  trust_level: TrustLevel;
  available_weight: number;
  credibility_basis: string;
  weights: Record<DimensionKey, number>;
  scores: Record<DimensionKey, number | null>;
  labels: Record<DimensionKey, string>;
  /** Whether an unavailable dimension is the platform's silence or this
   *  fetch's. They are different claims and must not share wording. */
  unavailable_because: "page" | "platform";
  evidence: Evidence;
  content_hash: string;
  rubric_version: string;
  checked_at: number;
  checker: string;
  fee_paid_wei: string;
}

export interface CheckMissing {
  found: false;
  reason: string;
  url_key?: string;
  platform?: string;
  check_id?: number;
  supported?: string[];
}

export type CheckResult = CheckRecord | CheckMissing;

export interface CheckSummary {
  check_id: number;
  url_key: string;
  platform: Platform;
  title: string;
  source_url: string;
  overall: number;
  trust_level: TrustLevel;
  reviews_parsed: number;
  total_ratings: number | null;
  avg_rating_x10: number | null;
  available_weight: number;
  checked_at: number;
}

export interface Stats {
  pages_tracked: number;
  total_requests: string;
  total_checked: number;
  authentic: number;
  suspicious: number;
  manipulated: number;
  inconclusive: number;
  manipulation_rate_pct: number;
  conclusive_checks: number;
  pages_by_platform: Record<Platform, number>;
  total_fees_wei: string;
  balance_wei: string;
  refunds_owed_wei: string;
  paused: boolean;
}

export interface PlatformConfig {
  hosts: string[];
  dimensions: Record<DimensionKey, boolean>;
  available_weight: number;
  credibility_basis: string;
}

export interface Config {
  rubric_version: string;
  owner: string;
  paused: boolean;
  fee_wei: string;
  max_fee_wei: string;
  rate_limit_seconds: number;
  url_cooldown_seconds: number;
  pending_ttl_seconds: number;
  history_cap: number;
  min_reviews: number;
  min_available_weight: number;
  quantisation_step: number;
  thresholds: { authentic_min: number; suspicious_min: number };
  trust_levels: TrustLevel[];
  weights: Record<DimensionKey, number>;
  buckets: Record<DimensionKey, string[]>;
  platforms: Record<Platform, PlatformConfig>;
  unsupported: Record<string, string>;
}

export interface Detection {
  supported: boolean;
  platform: Platform | "";
  url_key: string;
  canonical_url?: string;
  available_weight?: number;
  credibility_basis?: string;
  already_checked?: boolean;
  reason: string;
  platforms?: string[];
}

export interface VerifyResult {
  verified: boolean;
  check_id: number;
  url_key?: string;
  platform?: string;
  rubric_version?: string;
  current_rubric_version?: string;
  recomputed?: {
    scores: Record<DimensionKey, number | null>;
    overall: number;
    trust_level: TrustLevel;
    available_weight: number;
    content_hash: string;
  };
  mismatches?: { field: string; stored: unknown; recomputed: unknown }[];
  reason?: string;
}
