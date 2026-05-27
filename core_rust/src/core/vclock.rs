use std::time::{SystemTime, UNIX_EPOCH};

/// 仮想時間を表すラッパー型（ミリ秒単位）。
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct VTime(pub u64);

/// 実時間と進行倍率（レート）に基づいて仮想時間を管理する時計。
pub struct VClock {
    /// 仮想時間の起点となる実時間（エポックからのミリ秒）
    start_real_time: u64,
    /// 実時間に対する仮想時間の進行倍率
    rate: u64,
}

impl VClock {
    /// 新しい `VClock` インスタンスを生成します。
    ///
    /// * `start_time` - 仮想時計の起点とする実時間（エポックからのミリ秒）。
    /// * `rate` - 実時間に対する仮想時間の進行倍率。
    pub fn new(start_time: u64, rate: u64) -> Self {
        Self {
            start_real_time: start_time,
            rate,
        }
    }

    /// 現在の仮想時間を取得します。
    pub fn now(&self) -> VTime {
        let now_real = Self::current_real_time_millis();
        let real_diff = now_real.saturating_sub(self.start_real_time);
        VTime(real_diff * self.rate)
    }

    /// 現在のシステム時刻（実時間）をミリ秒単位で取得します。
    fn current_real_time_millis() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("Time went backwards")
            .as_millis() as u64
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread::sleep;
    use std::time::Duration;

    #[test]
    fn test_vclock_zero_rate() {
        let now = VClock::current_real_time_millis();
        let clock = VClock::new(now.saturating_sub(1000), 0);
        let time = clock.now();
        assert_eq!(time.0, 0);
    }

    #[test]
    fn test_vclock_future_start_time() {
        let now = VClock::current_real_time_millis();
        let clock = VClock::new(now + 10000, 1);
        let time = clock.now();
        assert_eq!(time.0, 0);
    }

    #[test]
    fn test_vclock_elapsed_time_and_scaling() {
        let now = VClock::current_real_time_millis();
        let rate = 2;
        // 開始時刻を 100ms 過去に設定
        let clock = VClock::new(now.saturating_sub(100), rate);

        let t1 = clock.now();
        // レートが2倍なので、100ms経過していれば200ms以上になっているはず
        assert!(
            t1.0 >= 200,
            "Expected at least 200 virtual ms, got {}",
            t1.0
        );

        // 10ms 実時間を進める
        sleep(Duration::from_millis(10));
        let t2 = clock.now();
        assert!(
            t2.0 > t1.0,
            "Time should advance. t1: {}, t2: {}",
            t1.0,
            t2.0
        );
    }
}
