import { getMerchantAvatarBg, getMerchantInitials } from "@/lib/format";

interface MerchantAvatarProps {
  name: string;
  category?: string;
  size?: "sm" | "md" | "lg" | "xl";
}

const SIZE_CLASSES = {
  sm: "w-9 h-9 text-sm",
  md: "w-11 h-11 text-base",
  lg: "w-14 h-14 text-lg",
  xl: "w-20 h-20 text-2xl",
};

export function MerchantAvatar({ name, category, size = "md" }: MerchantAvatarProps) {
  const bg = getMerchantAvatarBg(category);
  const initials = getMerchantInitials(name);
  const sizeClass = SIZE_CLASSES[size];

  return (
    <div
      className={`${sizeClass} ${bg} rounded-xl flex items-center justify-center text-white font-bold flex-shrink-0`}
      aria-label={name}
    >
      {initials}
    </div>
  );
}
