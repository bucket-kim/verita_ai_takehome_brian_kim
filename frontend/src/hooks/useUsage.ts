import { useState, useEffect, useCallback } from 'react';
import apiClient from '../api/client';
import type { UsageEvent, UsageResponse } from '../types';

interface UseUsageOptions {
  start?: string;
  end?: string;
  limit?: number;
}

export const useUsage = (options: UseUsageOptions = {}) => {
  const [events, setEvents] = useState<UsageEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const fetchUsage = useCallback(async (nextCursor?: string | null) => {
    try {
      setLoading(true);
      const params: Record<string, string | number> = {
        limit: options.limit || 1000,
      };

      if (options.start) params.start = options.start;
      if (options.end) params.end = options.end;
      if (nextCursor) params.cursor = nextCursor;

      const response = await apiClient.get<UsageResponse>('/v1/usage', { params });

      if (nextCursor) {
        // Append for pagination
        setEvents((prev) => [...prev, ...response.data.events]);
      } else {
        // Replace for initial load
        setEvents(response.data.events);
      }

      setCursor(response.data.next_cursor);
      setHasMore(response.data.has_more);
      setError(null);
    } catch (err) {
      setError('Failed to fetch usage data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [options.start, options.end, options.limit]);

  useEffect(() => {
    void fetchUsage();
  }, [fetchUsage]);

  const loadMore = () => {
    if (cursor && hasMore) {
      void fetchUsage(cursor);
    }
  };

  return { events, loading, error, hasMore, loadMore };
};
